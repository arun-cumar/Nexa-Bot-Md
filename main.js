import makeWASocket, { useMultiFileAuthState } from "@whiskeysockets/baileys";
import connectionHandler from "./settings/connection.js";
import messageHandler from "./messages.js"; 
import config from "./config.js";
import readline from "readline";

const question = (text) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    return new Promise((resolve) => rl.question(text, resolve));
};

async function startNexa() {
    const { state, saveCreds } = await useMultiFileAuthState('./session');

    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: !process.argv.includes('--pairing-code'),
        browser: [config.BOT_NAME, "Chrome", "1.0.0"]
    });

    if (!sock.authState.creds.registered && process.argv.includes('--pairing-code')) {
        const phoneNumber = await question('\n📞 Enter your Phone Number: ');
        const code = await sock.requestPairingCode(phoneNumber.replace(/[^0-9]/g, ''));
        console.log(`\x1b[32m\nYOUR 🗝 PAIRING CODE: \x1b[1m${code}\x1b[0m\n`);
    }

    connectionHandler(sock, startNexa, saveCreds);
    
    sock.ev.on('messages.upsert', async (chatUpdate) => {
        await messageHandler(sock, chatUpdate);
    });
}

startNexa();
