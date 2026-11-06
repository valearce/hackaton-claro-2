export function selectTarget(targets, { origin, target, worker = false }) {
    if (!origin && !target) throw new Error('Indica --origin URL o --target ID para seleccionar la pestaña.');
    const expectedOrigin = origin ? new URL(origin).origin : null;
    const candidates = targets.filter(item => {
        if (item.type !== (worker ? 'service_worker' : 'page')) return false;
        if (target && item.id !== target) return false;
        try { return !expectedOrigin || new URL(item.url).origin === expectedOrigin; }
        catch { return false; }
    });
    if (candidates.length !== 1) throw new Error(candidates.length ? 'Hay varias pestañas coincidentes. Usa --target ID.' : 'No se encontró una pestaña coincidente. Abre Chrome en el teléfono y usa tabs.');
    return candidates[0];
}

export class Cdp {
    constructor(socket) {
        this.socket = socket;
        this.sequence = 0;
        this.pending = new Map();
        this.onEvent = () => {};
        socket.addEventListener('message', event => {
            try {
                const value = JSON.parse(String(event.data));
                const task = this.pending.get(value.id);
                if (task) {
                    clearTimeout(task.timer); this.pending.delete(value.id);
                    if (value.error) task.reject(new Error(value.error.message));
                    else task.resolve(value.result);
                } else if (value.method) this.onEvent(value);
            } catch (error) { this.fail(error); }
        });
        socket.addEventListener('close', () => this.fail(new Error('Se cerró la conexión CDP.')));
        socket.addEventListener('error', () => this.fail(new Error('Error en la conexión CDP.')));
    }

    static async connect(url) {
        const socket = new WebSocket(url);
        await new Promise((resolve, reject) => {
            const finish = error => {
                clearTimeout(timer);
                socket.removeEventListener('open', onOpen);
                socket.removeEventListener('error', onError);
                socket.removeEventListener('close', onError);
                if (error) { socket.close(); reject(error); } else resolve();
            };
            const onOpen = () => finish();
            const onError = () => finish(new Error('No se pudo abrir la conexión CDP.'));
            const timer = setTimeout(() => finish(new Error('Timeout al conectar con CDP.')), 5000);
            socket.addEventListener('open', onOpen);
            socket.addEventListener('error', onError);
            socket.addEventListener('close', onError);
        });
        return new Cdp(socket);
    }

    fail(error) {
        for (const task of this.pending.values()) { clearTimeout(task.timer); task.reject(error); }
        this.pending.clear();
    }

    command(method, params = {}) {
        return new Promise((resolve, reject) => {
            const id = ++this.sequence;
            const timer = setTimeout(() => { this.pending.delete(id); reject(new Error(`Timeout en ${method}`)); }, 20000);
            this.pending.set(id, { resolve, reject, timer });
            try { this.socket.send(JSON.stringify({ id, method, params })); }
            catch (error) { clearTimeout(timer); this.pending.delete(id); reject(error); }
        });
    }

    async evaluate(expression) {
        const result = await this.command('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
        if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
        return result.result.value;
    }

    close() { this.fail(new Error('Conexión CDP finalizada.')); this.socket.close(); }
}
