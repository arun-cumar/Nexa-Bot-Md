import fs from "fs";
import path from "path";
import { pathToFileURL } from "url";
import config from "./config.js";
const toggleFile = "./media/toggles.json";

// load toggles
let toggles = {};
if (fs.existsSync(toggleFile)) {
    toggles = JSON.parse(fs.readFileSync(toggleFile));
}

// save toggles
const saveToggles = () => {
    fs.writeFileSync(toggleFile, JSON.stringify(toggles, null, 2));
};

export default async (sock, chatUpdate) => {

    try {

        const msg = chatUpdate.messages?.[0];
        if (!msg || !msg.message) return;
        if (msg.key.remoteJid === "status@broadcast") return;

        const from = msg.key.remoteJid;
        const sender = msg.key.participant || msg.key.remoteJid;

        const body =
            msg.message.conversation ||
            msg.message.extendedTextMessage?.text ||
            "";

        const text = body.trim();
        const isCmd = text.startsWith(config.PREFIX);

        const commandName = isCmd
            ? text.slice(config.PREFIX.length).split(" ")[0].toLowerCase()
            : "";

        const args = text.split(/ +/).slice(1);

       // Global Mode Check (Public/Private)
if (!toggles.global) toggles.global = { mode: "public" };

if (commandName === "mode") {
    const newMode = args[0]?.toLowerCase();
    if (newMode === "public" || newMode === "private") {
        toggles.global.mode = newMode;
        saveToggles();
        return await sock.sendMessage(from, { text: `✅ Bot mode changed to *${newMode}*` }, { quoted: msg });
    }
}

// Private mode 
const isOwner = config.OWNER_NUMBER.includes(sender.split('@')[0]);
if (toggles.global.mode === "private" && !isOwner) return;

        if (!isCmd) return;

        const commandPath = path.join(process.cwd(), "plugins", `${commandName}.js`);

        if (!fs.existsSync(commandPath)) {
            console.log(`\x1b[33m[NOT FOUND] -> ${commandName}\x1b[0m`);
            return;
        }

        await sock.sendPresenceUpdate("composing", from);

        const moduleUrl = pathToFileURL(commandPath).href + `?update=${Date.now()}`;
        const commandModule = await import(moduleUrl);

        const handler = commandModule.default || commandModule.run;

        // toggle system
        if (args[0] === "on" || args[0] === "off") {

            const state = args[0] === "on";

            if (!toggles[from]) toggles[from] = {};

            toggles[from][commandName] = state;

            saveToggles();

            await sock.sendMessage(from, {
                text: `⚙️ *${commandName}*\nStatus: ${state ? "🟢 Enabled" : "🔴 Disabled"}`
            }, { quoted: msg });

            return;
        }

        // check toggle
        if (toggles[from]?.[commandName] === false) {

            return await sock.sendMessage(from, {
                text: `⚠️ *${commandName}* is currently disabled`
            }, { quoted: msg });

        }

        if (handler) {

            await handler(sock, msg, args, { toggles });

            console.log(`\x1b[32m[SUCCESS] -> ${commandName} executed\x1b[0m`);

        }

    } catch (err) {

        console.error("Message Error:", err);

    }
};
