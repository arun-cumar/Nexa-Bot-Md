// © 2026 arun•°Cumar. All Rights Reserved.
import fs from 'fs';
import path from 'path';
import config from '../config.js';
import menuDesigns from '../lib/menu.js';
import { sendInteractiveMessage } from '../settings/interactive.js';

export default async (sock, msg, args) => {
    try {
        const from = msg.key.remoteJid;
        const sender = msg.key.participant || from;

        const commandsDir = path.join(process.cwd(), 'commands');
        const files = fs.readdirSync(commandsDir).filter(file => file.endsWith('.js'));

        // Command list create
        let commandList = '';
        files.forEach((file, index) => {
            const cmdName = file.replace('.js', '');
            commandList += `${index + 1}. ${config.PREFIX}${cmdName}\n`;
        });

        // design
        const randomDesign = menuDesigns[Math.floor(Math.random() * menuDesigns.length)];

        const menuText = randomDesign
            .replace('{bot}', config.BOT_NAME)
            .replace('{user}', sender.split('@')[0])
            .replace('{date}', new Date().toLocaleDateString())
            .replace('{prefix}', config.PREFIX)
            .replace('{commands}', commandList);

        // Interactive Buttons
        const buttons = [
            {
                name: "quick_reply",
                buttonParamsJson: JSON.stringify({
                    display_text: "⚡ Ping",
                    id: `${config.PREFIX}ping`
                })
            },
            {
                name: "quick_reply",
                buttonParamsJson: JSON.stringify({
                    display_text: "🟢 Alive",
                    id: `${config.PREFIX}alive`
                })
            }
        ];

        // Send Interactive Menu
        await sendInteractiveMessage(sock, from, {
            text: menuText,
            footer: config.BOT_NAME,
            buttons: buttons
        }, { quoted: msg });

    } catch (err) {
        console.log(err);
    }
};
