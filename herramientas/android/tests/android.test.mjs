import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { Android, findAdb, notificationImage, parseDevices, shellQuote } from '../lib/adb.mjs';
import { parseArguments } from '../android.mjs';
import { Cdp, selectTarget } from '../lib/cdp.mjs';

function tempDirectory(t) {
    const root = mkdtempSync(join(tmpdir(), 'claro-android-test-'));
    t.after(() => {
        const absolute = resolve(root);
        if (dirname(absolute) !== resolve(tmpdir()) || !basename(absolute).startsWith('claro-android-test-')) throw new Error('Directorio de prueba fuera del destino permitido.');
        rmSync(absolute, { recursive: true, force: true });
    });
    return root;
}

test('lista dispositivos autorizados, offline y sin autorización', () => {
    assert.deepEqual(parseDevices('List of devices attached\r\nA device product:phone\r\nB unauthorized\r\nC offline\r\n'), [
        { serial: 'A', state: 'device' }, { serial: 'B', state: 'unauthorized' }, { serial: 'C', state: 'offline' },
    ]);
});

test('rechaza selección ambigua y dispositivo no autorizado', async () => {
    const run = async () => 'A device\nB device\nC unauthorized';
    await assert.rejects(new Android('adb', undefined, { run }).select(), /varios dispositivos/);
    await assert.rejects(new Android('adb', 'C', { run }).select(), /unauthorized/);
    assert.equal(await new Android('adb', 'B', { run }).select(), 'B');
});

test('el texto con apóstrofes y metacaracteres se mantiene como un argumento de sh', async () => {
    const calls = [];
    const android = new Android('adb', 'PHONE', { run: async (...args) => { calls.push(args); return 'posted'; } });
    const text = "Oferta 'especial'; $(reboot) & prueba";
    await android.notify({ text, show: true });
    assert.deepEqual(calls[0][1].slice(0, 3), ['-s', 'PHONE', 'shell']);
    assert.ok(calls[0][1][3].includes("'Oferta '\\''especial'\\''; $(reboot) & prueba'"));
    assert.ok(calls[1][1][3].includes("'expand-notifications'"));
    assert.throws(() => shellQuote('texto\0'), /NUL/);
});

test('rechaza opciones equivocadas y no ignora un mensaje accidental en record', () => {
    assert.throws(() => parseArguments(['record', '--text', 'hola']), /Opción desconocida/);
    assert.throws(() => parseArguments(['demo', '--seconds']), /Falta el valor/);
    assert.throws(() => parseArguments(['demo', '--text', 'hola', '--text', 'otro']), /repetida/);
    assert.equal(parseArguments(['demo', '--text', 'hola', '--show']).options.show, true);
    assert.equal(parseArguments(['demo', '--text', 'hola', '--popup']).options.popup, true);
});

test('el aviso flotante usa el canal propio y mantiene cerrada la bandeja', async t => {
    const dex = join(tempDirectory(t), 'popup.dex');
    writeFileSync(dex, 'dex de prueba');
    const calls = [];
    const android = new Android('adb', 'PHONE', { popupDex: dex, run: async (file, args) => {
        calls.push(args);
        return args[3]?.includes("'app_process'") ? 'popup-posted' : '';
    } });
    const result = await android.notify({ popup: true, text: "DEMO 'oferta'" });
    assert.equal(result.kind, 'local-popup');
    assert.equal(result.panelOpened, false);
    assert.equal(calls[0][2], 'push');
    assert.ok(calls[1][3].includes("'DEMO '\\''oferta'\\'''"));
    assert.ok(calls[2][3].startsWith("'rm' '-f' '/data/local/tmp/claro-demo-popup-"));
    assert.ok(!calls.some(args => args[3]?.includes('expand-notifications')));
});

test('popup y apertura de la bandeja se rechazan antes de actuar sobre el teléfono', async () => {
    const android = new Android('adb', 'PHONE', { run: async () => { throw new Error('No debe ejecutar ADB'); } });
    await assert.rejects(android.notify({ popup: true, show: true, text: 'DEMO' }), /--popup sin --show/);
    await assert.rejects(android.record({ popup: true, show: true, message: 'DEMO' }), /--popup sin --show/);
});

function imageFixture(t) {
    const root = tempDirectory(t);
    const image = join(root, 'imagen de prueba.png');
    const dex = join(root, 'popup.dex');
    writeFileSync(image, Buffer.from('89504e470d0a1a0a', 'hex'));
    writeFileSync(dex, 'dex de prueba');
    return { image, dex };
}

test('transfiere imagen y auxiliar, los retira juntos y mantiene cerrada la bandeja', async t => {
    const { image, dex } = imageFixture(t);
    const calls = [];
    const android = new Android('adb', 'PHONE', { popupDex: dex, run: async (file, args) => {
        calls.push(args);
        return args[3]?.includes("'app_process'") ? 'popup-posted' : '';
    } });
    assert.equal((await android.notify({ text: 'DEMO', popup: true, image })).image, image);
    assert.equal(calls.filter(args => args[2] === 'push').length, 2);
    assert.equal(calls[1][3], image);
    assert.ok(calls[3][3].includes('.dex') && calls[3][3].includes('.image'));
    assert.ok(!calls.some(args => args[3]?.includes('expand-notifications')));
});

test('rechaza imágenes incompatibles, ausentes o grandes antes de usar ADB', async t => {
    const root = tempDirectory(t);
    const invalid = join(root, 'falso.png');
    writeFileSync(invalid, 'no es una imagen');
    assert.throws(() => notificationImage(invalid), /PNG o JPEG válida/);
    assert.throws(() => notificationImage(join(root, 'ausente.jpg')), /no existe/);
    const large = join(root, 'grande.png');
    writeFileSync(large, Buffer.alloc(5 * 1024 * 1024 + 1));
    assert.throws(() => notificationImage(large), /5 MB/);
    const android = new Android('adb', 'PHONE', { run: async () => { throw new Error('No debe ejecutar ADB'); } });
    await assert.rejects(android.notify({ text: 'DEMO', image: invalid }), /requiere --popup/);
    await assert.rejects(android.record({ message: 'DEMO', popup: true, image: invalid }), /PNG o JPEG válida/);
});

test('el banner conserva los permisos y verifica apertura y cierre', async t => {
    const { image, dex } = imageFixture(t);
    const calls = [];
    const android = new Android('adb', 'PHONE', { popupDex: dex, run: async (file, args) => {
        calls.push(args);
        if (args[3]?.includes("'appops' 'get'")) return 'No operations.\nDefault mode: default';
        if (args[3]?.includes("'app_process'")) return 'banner-shown\nbanner-closed';
        return '';
    } });
    const result = await android.banner({ title: 'DEMO', text: 'Contenido', image, seconds: 10 });
    assert.equal(result.kind, 'demo-banner');
    assert.equal(result.permissionUnchanged, true);
    assert.ok(!calls.some(args => args[3]?.includes("'appops' 'set'")));
    assert.ok(calls.at(-1)[3].startsWith("'rm' '-f'"));
});

test('un bloqueo de superposición impide publicar el banner', async t => {
    const { image, dex } = imageFixture(t);
    let calls = 0;
    const android = new Android('adb', 'PHONE', { popupDex: dex, run: async () => {
        calls++;
        return 'SYSTEM_ALERT_WINDOW: ignore';
    } });
    await assert.rejects(android.banner({ text: 'DEMO', image }), /bloqueada/);
    assert.equal(calls, 1);
});

test('la CLI acepta rutas de imagen con espacios', () => {
    const parsed = parseArguments(['banner', '--image', 'carpeta/logo claro.jpg', '--text', 'DEMO', '--seconds', '15']);
    assert.equal(parsed.options.image, 'carpeta/logo claro.jpg');
    assert.equal(parseArguments(['notify', '--popup', '--image', 'logo.jpg']).options.image, 'logo.jpg');
    const sms = parseArguments(['sms-demo', '--sender', 'Claro', '--text', 'DEMO', '--image', 'logo claro.jpg']);
    assert.equal(sms.options.sender, 'Claro');
    assert.equal(sms.options.image, 'logo claro.jpg');
});

function fakeRecording(t, { noticeFails = false, pullFails = false } = {}) {
    const calls = [];
    let finish;
    const root = tempDirectory(t);
    const output = join(root, 'demo.mp4');
    const run = async (file, args) => {
        assert.equal(file, 'adb');
        assert.deepEqual(args.slice(0, 2), ['-s', 'PHONE']);
        calls.push(args.slice(2));
        const command = args[3] || '';
        if (args[2] === 'shell' && command.startsWith("'screenrecord'")) return new Promise(resolve => { finish = resolve; });
        if (command.startsWith('if test')) return 'ready';
        if (command.includes("'notification' 'post'")) {
            finish('');
            if (noticeFails) throw new Error('notificaciones deshabilitadas');
            return 'posting';
        }
        if (args[2] === 'pull') {
            if (pullFails) throw new Error('transferencia fallida');
            writeFileSync(args[4], 'video de prueba');
        }
        return '';
    };
    return { android: new Android('adb', 'PHONE', { run, wait: async () => {} }), calls, output };
}

test('demo espera el inicio, publica el aviso y descarga antes de retirar el video remoto', async t => {
    const { android, output, calls } = fakeRecording(t);
    const result = await android.record({ seconds: 10, delay: 2, message: 'DEMO', output, show: true });
    assert.equal(result.output, output);
    assert.equal(readFileSync(output, 'utf8'), 'video de prueba');
    assert.ok(calls.findIndex(args => args[1]?.startsWith('if test')) < calls.findIndex(args => args[1]?.includes("'notification' 'post'")));
    assert.ok(calls.findIndex(args => args[0] === 'pull') < calls.findIndex(args => args[1]?.startsWith("'rm'")));
});

test('conserva el video local si falla la notificación e informa el fallo', async t => {
    const { android, output } = fakeRecording(t, { noticeFails: true });
    await assert.rejects(android.record({ seconds: 10, message: 'DEMO', output }), /Video guardado.*falló el aviso/);
    assert.equal(readFileSync(output, 'utf8'), 'video de prueba');
});

test('no retira el video del teléfono si falla la descarga', async t => {
    const { android, output, calls } = fakeRecording(t, { pullFails: true });
    await assert.rejects(android.record({ seconds: 10, message: 'DEMO', output }), /transferencia fallida/);
    assert.ok(!calls.some(args => args[1]?.startsWith("'rm'")));
});

test('no graba encima de un archivo existente ni acepta duración inválida', async t => {
    const output = join(tempDirectory(t), 'anterior.mp4');
    writeFileSync(output, 'conservar');
    const android = new Android('adb', 'PHONE', { run: async () => { throw new Error('No debe ejecutar ADB'); } });
    await assert.rejects(android.record({ output }), /ya existe/);
    await assert.rejects(android.record({ seconds: 181 }), /entre 1 y 180/);
    assert.equal(readFileSync(output, 'utf8'), 'conservar');
});

test('una ruta ADB configurada incorrecta no se sustituye silenciosamente', () => {
    assert.throws(() => findAdb('/adb-inexistente-de-prueba', {}, {}), /ADB no encontrado/);
});

test('CDP exige un origen exacto y selección explícita cuando hay varias pestañas', () => {
    const targets = [
        { id: '1', type: 'page', url: 'https://claro.example/mapa' },
        { id: '2', type: 'page', url: 'https://claro.example.evil/mapa' },
    ];
    assert.equal(selectTarget(targets, { origin: 'https://claro.example' }).id, '1');
    assert.throws(() => selectTarget(targets, {}), /Indica --origin/);
    assert.throws(() => selectTarget([...targets, { ...targets[0], id: '3' }], { origin: 'https://claro.example' }), /varias pestañas/);
});

test('CDP rechaza comandos pendientes al desconectarse y libera temporizadores', async () => {
    const socket = new EventTarget();
    socket.send = () => {};
    socket.close = () => socket.dispatchEvent(new Event('close'));
    const cdp = new Cdp(socket);
    const request = cdp.command('Runtime.evaluate');
    socket.close();
    await assert.rejects(request, /Se cerró/);
    assert.equal(cdp.pending.size, 0);
});
