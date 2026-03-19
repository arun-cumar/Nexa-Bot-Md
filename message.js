import path from "path";
import { pathToFileURL } from "url";
import fs from "fs";
import { getToggles } from "./lib/toggles.js";
import { parseMessage } from "./lib/msgHelper.js";
import { executeCommand } from "./lib/loader.js";
import config from "./config.js";

export default async (sock, chatUpdate) => {
    try {
        const msg = chatUpdate.messages?.[0];
        if (!msg || !msg.message || msg.key.remoteJid === "status@broadcast") return;

        const from = msg.key.remoteJid;
        const sender = msg.key.participant || msg.key.remoteJid;
        const senderNumber = sender.replace(/\D/g, ''); 

        // 2. Owner checking
        const isOwner = config.OWNER_NUMBER.some(num => num.replace(/\D/g, '') === senderNumber) || msg.key.fromMe;

        // 3. Mention Sticker Logic
        const mentions = msg.message?.extendedTextMessage?.contextInfo?.mentionedJid || [];
        if (mentions.length > 5) {
            const stickerPath = './media/sticker.webp';
            if (fs.existsSync(stickerPath)) {
                await sock.sendMessage(from, {
                    sticker: fs.readFileSync(stickerPath)
                }, { quoted: msg });
            }
        }

        // 4. Parse Message    
        const { isCmd, commandName, args } = parseMessage(msg);    
        if (!isCmd || !commandName) return;    

        // 5. Get Toggles & Command Status Check
        const toggles = getToggles();    
        if (toggles[commandName]?.status === "off") return;    

        // 6. Global Public/Private Mode Check   
        if (global.isPublic === false && !isOwner) return;  

        // 7. Specific Command Private Check   
        if (toggles[commandName]?.mode === "private" && !isOwner) {  
            return await sock.sendMessage(from, { text: "🔒 This command is for my Owner only." });  
        }  

        // 8. Execute Command  
        await executeCommand(commandName, sock, msg, args, { toggles, isOwner });

    } catch (err) {    
        console.error("❌ Message Error:", err);    
    }
};





