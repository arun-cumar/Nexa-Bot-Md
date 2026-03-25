// © 2026 arun•°Cumar. All Rights Reserved.
import fs from 'fs';
import config from "../config.js";
import { DisconnectReason } from '@whiskeysockets/baileys';

const dbPath = './database/connection.json';

function saveConnectionData(data) {
    let json = {};

    if (fs.existsSync(dbPath)) {
        json = JSON.parse(fs.readFileSync(dbPath));
    }

    const newData = { ...json, ...data };
    fs.writeFileSync(dbPath, JSON.stringify(newData, null, 2));
}

const connection = async (sock, startNexa, saveCreds) => {

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect } = update;

        if (connection === 'close') {
            const reason = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = reason !== DisconnectReason.loggedOut;

            console.log(`❌ Connection Closed. Reason: ${reason}`);

            // Save disconnect info
            saveConnectionData({
                status: "offline",
                lastDisconnect: new Date().toISOString()
            });

            if (shouldReconnect) {
                console.log("🔁 Reconnecting...");
                
                // Increase reconnect count
                let data = {};
                if (fs.existsSync(dbPath)) {
                    data = JSON.parse(fs.readFileSync(dbPath));
                }

                saveConnectionData({
                    reconnects: (data.reconnects || 0) + 1
                });

                startNexa();
            }
        } 
        
        else if (connection === 'open') {
            console.log('\x1b[36m✅ Nexa-Bot MD Connected Successfully!\x1b[0m');

            // Save connect info
            saveConnectionData({
                status: "online",
                lastConnect: new Date().toISOString()
            });

            const myNumber = sock.user.id.split(':')[0] + "@s.whatsapp.net";

            const activeMsg = `
╭━━〔 ${config.BOT_NAME} 〕━━╮
┃ 🛠️ STATUS: Online
┃ 👤 OWNER: ${config.OWNER_NAME}
┃ 📞 CONTACT: ${config.OWNER_NUMBER}
┃ ⚡ PREFIX: ${config.PREFIX}
┃ 📝 DESC: ${config.DESCRIPTION}
╰━━━━━━━━━━━━━━━╯`;

            try {
                const imagePath = './media/nexa.jpg';
                if (fs.existsSync(imagePath)) {
                    await sock.sendMessage(myNumber, { 
                        image: fs.readFileSync(imagePath), 
                        caption: activeMsg 
                    });
                } else {
                    await sock.sendMessage(myNumber, { text: activeMsg });
                }
            } catch (err) {
                console.log("❌ Login Notification Error:", err.message);
            }
        }
    });

    sock.ev.on('creds.update', saveCreds);
};

export default connection;
