import { execFile } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, statSync } from 'node:fs';
import { delimiter, dirname, extname, isAbsolute, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { setTimeout as sleep } from 'node:timers/promises';

export const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');

export function readConfig(root = projectRoot) {
    const file = join(root, '.local/android/config.json');
    return existsSync(file) ? JSON.parse(readFileSync(file, 'utf8').replace(/^\uFEFF/, '')) : {};
}

export function findAdb(explicit, config = {}, env = process.env) {
    const executable = process.platform === 'win32' ? 'adb.exe' : 'adb';
    const configured = explicit || env.ADB_PATH || config.adbPath;
    const candidates = configured ? [resolve(projectRoot, configured)] : [
        join(projectRoot, '.local/android/platform-tools', executable),
        ...[env.ANDROID_HOME, env.ANDROID_SDK_ROOT, env.LOCALAPPDATA && join(env.LOCALAPPDATA, 'Android/Sdk')]
            .filter(Boolean).map(root => join(root, 'platform-tools', executable)),
        ...(env.PATH || '').split(delimiter).filter(Boolean).map(root => join(root, executable)),
    ];
    const found = candidates.find(file => existsSync(file) && statSync(file).isFile());
    if (!found) throw new Error('ADB no encontrado. Usa --adb RUTA, ADB_PATH o .local/android/config.json.');
    return found;
}

// ADB pasa los comandos de shell a Android: el escapado corresponde a sh, no a PowerShell.
export function shellQuote(value) {
    const text = String(value);
    if (text.includes('\0')) throw new Error('Los argumentos no pueden contener NUL.');
    return "'" + text.replaceAll("'", "'\\''") + "'";
}

export function parseDevices(output) {
    return output.split(/\r?\n/).flatMap(line => {
        const match = line.match(/^(\S+)\s+(device|offline|unauthorized)(?:\s|$)/);
        return match ? [{ serial: match[1], state: match[2] }] : [];
    });
}

export function runProcess(file, args, timeout = 20000) {
    return new Promise((accept, reject) => {
        execFile(file, args, { windowsHide: true, shell: false, timeout, maxBuffer: 16 * 1024 * 1024, encoding: 'utf8' },
            (error, stdout, stderr) => {
                if (error) reject(new Error((stderr || stdout || error.message).trim()));
                else accept(stdout.trim());
            });
    });
}

export function boundedInteger(value, name, min, max) {
    const number = Number(value);
    if (!Number.isInteger(number) || number < min || number > max) {
        throw new Error(`${name} debe ser un entero entre ${min} y ${max}.`);
    }
    return number;
}

export function notificationImage(image) {
    if (image === undefined) return undefined;
    const file = resolve(image);
    if (!existsSync(file) || !statSync(file).isFile()) throw new Error('La imagen no existe o no es un archivo.');
    if (statSync(file).size > 5 * 1024 * 1024) throw new Error('La imagen debe pesar como máximo 5 MB.');
    const header = readFileSync(file).subarray(0, 8);
    const png = header.equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
    const jpeg = header[0] === 255 && header[1] === 216 && header[2] === 255;
    if (!png && !jpeg) throw new Error('Usa una imagen PNG o JPEG válida.');
    return file;
}

export class Android {
    constructor(adbPath, serial, { run = runProcess, wait = sleep, popupDex = join(projectRoot, '.local/android/popup/classes.dex') } = {}) {
        this.adbPath = adbPath;
        this.serial = serial;
        this.run = run;
        this.wait = wait;
        this.popupDex = popupDex;
    }

    async devices() { return parseDevices(await this.run(this.adbPath, ['devices', '-l'])); }

    async select() {
        const devices = await this.devices();
        if (this.serial) {
            const device = devices.find(item => item.serial === this.serial);
            if (!device || device.state !== 'device') throw new Error(`Dispositivo ${this.serial}: ${device?.state || 'no conectado'}. Autoriza la depuración USB en el teléfono.`);
        } else {
            const ready = devices.filter(item => item.state === 'device');
            if (ready.length !== 1) throw new Error(ready.length ? 'Hay varios dispositivos. Indica --serial SERIAL.' : 'No hay un dispositivo autorizado. Conecta el teléfono y acepta la depuración USB.');
            this.serial = ready[0].serial;
        }
        return this.serial;
    }

    device(args, timeout) {
        if (!this.serial) throw new Error('Selecciona primero un dispositivo.');
        return this.run(this.adbPath, ['-s', this.serial, ...args], timeout);
    }

    shell(args, timeout) { return this.device(['shell', args.map(shellQuote).join(' ')], timeout); }

    async smsDemo({ sender = 'Claro', text, image }) {
        if (!image) throw new Error('Indica --image para el aviso de mensaje con imagen.');
        const result = await this.notify({ title: sender, text, image, popup: true });
        return { ...result, kind: 'sms-style-demo', sender, actualSms: false };
    }

    async banner({ title = 'Una oferta para ti', text, image, seconds = 15 }) {
        if (!text?.trim()) throw new Error('Indica --text con el contenido del banner.');
        if (!image) throw new Error('Indica --image con la imagen del banner.');
        seconds = boundedInteger(seconds, '--seconds', 3, 60);
        const imageFile = notificationImage(image);
        if (!existsSync(this.popupDex)) throw new Error('Prepara el banner con node herramientas/android/build-popup.mjs.');
        const permission = await this.shell(['cmd', 'appops', 'get', 'com.android.shell', 'SYSTEM_ALERT_WINDOW']);
        const mode = permission.match(/(?:SYSTEM_ALERT_WINDOW:|Default mode:)\s*(allow|ignore|deny|default|foreground)\b/)?.[1];
        if (!mode) throw new Error('No se pudo determinar el permiso original de superposición.');
        if (!['allow', 'default'].includes(mode)) throw new Error(`La superposición de Android Shell está bloqueada (${mode}).`);
        const remote = `/data/local/tmp/claro-demo-banner-${randomUUID()}`;
        const cleanupErrors = [];
        let failure;
        try {
            await this.device(['push', this.popupDex, `${remote}.dex`]);
            await this.device(['push', imageFile, `${remote}.image`]);
            const result = await this.shell(['env', `CLASSPATH=${remote}.dex`, 'app_process', '/', 'com.claro.tools.Banner', title, text, `${remote}.image`, seconds * 1000], (seconds + 15) * 1000);
            if (!result.includes('banner-shown') || !result.includes('banner-closed')) throw new Error('Android no confirmó el ciclo completo del banner.');
        } catch (error) { failure = error; }
        finally {
            try { await this.shell(['rm', '-f', `${remote}.dex`, `${remote}.image`]); }
            catch (error) { cleanupErrors.push(`Retirar auxiliares: ${error.message}`); }
        }
        if (failure) throw new Error([failure.message, ...cleanupErrors].join('\n'));
        return { serial: this.serial, kind: 'demo-banner', title, text, image: imageFile, seconds, permissionUnchanged: true, cleanupErrors };
    }

    async notify({ title = 'Claro - Demo', text, show = false, popup = false, tag = 'claro-demo', image }) {
        if (!text?.trim()) throw new Error('Indica --text con el mensaje de prueba.');
        if (popup && show) throw new Error('Usa --popup sin --show para mantener cerrada la bandeja.');
        if (image !== undefined && !popup) throw new Error('--image requiere --popup.');
        const imageFile = notificationImage(image);
        if (popup) {
            const dex = this.popupDex;
            if (!existsSync(dex)) throw new Error('Prepara el canal flotante con node herramientas/android/build-popup.mjs.');
            const remote = `/data/local/tmp/claro-demo-popup-${randomUUID()}.dex`;
            const remoteImage = imageFile ? remote.replace(/\.dex$/, '.image') : undefined;
            let cleanupError;
            try {
                await this.device(['push', dex, remote]);
                if (imageFile) await this.device(['push', imageFile, remoteImage]);
                const posted = await this.shell(['env', `CLASSPATH=${remote}`, 'app_process', '/', 'com.claro.tools.Popup', title, text, ...(remoteImage ? [remoteImage] : [])]);
                if (!posted.includes('popup-posted')) throw new Error('Android no confirmó la notificación flotante.');
            } finally {
                try { await this.shell(['rm', '-f', remote, ...(remoteImage ? [remoteImage] : [])]); } catch (error) { cleanupError = error.message; }
            }
            return { serial: this.serial, kind: 'local-popup', title, text, image: imageFile, panelOpened: false, cleanupError };
        }
        const result = await this.shell(['cmd', 'notification', 'post', '-S', 'bigtext', '--bigtext', text, '-t', title, tag, text]);
        // Algunos fabricantes imprimen el error aunque el proceso termine con código cero.
        if (/^(?:Error|Exception|Unknown command|usage:)/im.test(result)) throw new Error(result);
        if (show) await this.shell(['cmd', 'statusbar', 'expand-notifications']);
        return { serial: this.serial, kind: 'local-notification', title, text, panelOpened: show };
    }

    async record({ seconds = 20, output, message, delay = 3, title, show = false, popup = false, image }) {
        if (popup && show) throw new Error('Usa --popup sin --show para mantener cerrada la bandeja.');
        if (image !== undefined && !popup) throw new Error('--image requiere --popup.');
        const imageFile = notificationImage(image);
        seconds = boundedInteger(seconds, '--seconds', 1, 180);
        if (message !== undefined) {
            if (!message.trim()) throw new Error('El mensaje de prueba no puede estar vacío.');
            delay = boundedInteger(delay, '--delay', 0, seconds - 1);
        }
        const destination = output
            ? (isAbsolute(output) ? output : resolve(process.cwd(), output))
            : join(projectRoot, '.local/android/grabaciones', `demo-${Date.now()}-${randomUUID().slice(0, 8)}.mp4`);
        if (extname(destination).toLowerCase() !== '.mp4') throw new Error('--output debe terminar en .mp4.');
        if (existsSync(destination)) throw new Error('El archivo de salida ya existe; elige otro nombre.');
        mkdirSync(dirname(destination), { recursive: true });
        const remote = `/sdcard/Download/claro-demo-${randomUUID()}.mp4`;
        const recording = this.shell(['screenrecord', '--time-limit', seconds, remote], (seconds + 20) * 1000);
        // El observador evita rechazos sin manejar mientras se espera el inicio del archivo.
        recording.catch(() => {});
        const notification = message === undefined ? Promise.resolve() : (async () => {
            const earlyEnd = recording.then(() => { throw new Error('La grabación terminó antes del aviso.'); });
            // Espera evidencia del archivo, sin depender sólo de un temporizador fijo.
            let started = false;
            for (let attempt = 0; attempt < 20; attempt++) {
                const ready = await Promise.race([
                    this.device(['shell', `if test -s ${shellQuote(remote)}; then echo ready; fi`]), earlyEnd,
                ]);
                if (ready === 'ready') { started = true; break; }
                await Promise.race([this.wait(200), earlyEnd]);
            }
            if (!started) throw new Error('No se pudo confirmar el inicio de screenrecord.');
            await Promise.race([this.wait(delay * 1000), earlyEnd]);
            return this.notify({ title, text: message, show, popup, image: imageFile });
        })();
        const [video, notice] = await Promise.allSettled([recording, notification]);
        if (video.status === 'rejected') {
            throw new Error(`Falló la grabación: ${video.reason.message}. Archivo remoto conservado: ${remote}`);
        }
        await this.device(['pull', remote, destination], 60000);
        if (!existsSync(destination) || statSync(destination).size === 0) {
            throw new Error(`La descarga está vacía; se conservó ${remote} en el teléfono.`);
        }
        // Sólo se retira nuestro archivo remoto tras verificar la copia local.
        let cleanupError;
        try { await this.shell(['rm', '-f', remote]); } catch (error) { cleanupError = error.message; }
        const result = { serial: this.serial, output: destination, seconds, notification: notice.status === 'fulfilled' ? notice.value : undefined, cleanupError };
        if (notice.status === 'rejected') throw new Error(`Video guardado en ${destination}; falló el aviso: ${notice.reason.message}`);
        return result;
    }
}
