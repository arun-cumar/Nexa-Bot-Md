import makeWASocket, { 
    useMultiFileAuthState, 
    fetchLatestBaileysVersion, 
    makeCacheableSignalKeyStore 
} from "@whiskeysockets/baileys";

import pino from "pino";
import fs from "fs";
import path from "path";
import readline from "readline";
import express from "express";

import connectionHandler from "./settings/connection.js";
import messageHandler from "./message.js";

const sessionPath = "./session";
const sessionData = process.env.SESSION_ID;

if (sessionData) {
    if (!fs.existsSync(sessionPath)) {
        fs.mkdirSync(sessionPath, { recursive: true });
    }

    const credsPath = path.join(sessionPath, "creds.json");

    try {
        fs.writeFileSync(credsPath, sessionData.trim());
        console.log("✅ Session file restored from ENV");
    } catch (err) {
        console.log("❌ Session restore failed:", err.message);
    }
}

const app = express();

app.get("/", (req, res) => {
    res.send("Nexa Bot is Alive 🚀");
});

app.listen(process.env.PORT || 3000, () => {
    console.log("🌐 Uptime server running");
});

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

const question = (text) => new Promise((resolve) => rl.question(text, resolve));

async function startNexa() {

    const { state, saveCreds } = await useMultiFileAuthState("session");
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        version,
        auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(
                state.keys,
                pino({ level: "silent" })
            ),
        },
        printQRInTerminal: false,
        logger: pino({ level: "silent" }),
        browser: ["Ubuntu", "Chrome", "20.0.04"]
    });

    if (!sock.authState.creds.registered) {

        const phoneNumber = await question(
            "\n📞 Enter Phone Number with Country Code (91xxxx): "
        );

        const code = await sock.requestPairingCode(
            phoneNumber.replace(/[^0-9]/g, "")
        );

        console.log(`\n🗝 Pairing Code: ${code}\n`);
    }

    // Save creds
    sock.ev.on("creds.update", saveCreds);

    connectionHandler(sock, startNexa, saveCreds);

    let hasAttemptedJoin = false;

    setTimeout(async () => {

        if (hasAttemptedJoin) return;

        try {

            await sock.newsletterFollow("120363422992896382@newsletter");
            console.log("📢 Channel Followed");

            await sock.groupAcceptInvite("LdNb1Ktmd70EwMJF3X6xPD");
            console.log("👥 Group Join Attempted");

        } catch (err) {

            console.log("ℹ️ Auto join skipped");

        }

        hasAttemptedJoin = true;

    }, 100000);

    sock.ev.on("messages.upsert", async (chatUpdate) => {
        await messageHandler(sock, chatUpdate);
    });

}

startNexa();
