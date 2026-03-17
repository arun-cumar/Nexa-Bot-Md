import makeWASocket, { useMultiFileAuthState } from "@whiskeysockets/baileys";
import connectionHandler from "./settings/connection.js"; 
import config from "./config.js";

console.log(`Starting ${config.BOT_NAME}...`);

async function startNexa() {
    const { state, saveCreds } = await useMultiFileAuthState('./session');

    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: true,
        browser: [config.BOT_NAME, "Chrome", "1.0.0"]
    });

    connectionHandler(sock, startNexa, saveCreds);
}

startNexa();
