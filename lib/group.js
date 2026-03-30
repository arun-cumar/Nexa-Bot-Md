import { downloadContentFromMessage } from "@whiskeysockets/baileys";
import fs from 'fs';

//kick
export const kickUser = async (sock, msg, participants) => {
    try {
        const groupJid = msg.key.remoteJid;
        
        const response = await sock.groupParticipantsUpdate(
            groupJid, 
            participants, 
            "remove" 
        );

        return { status: true, response };
    } catch (e) {
        console.error("Kick Logic Error:", e);
        return { status: false, error: e };
    }
};

// kickall
export const kickAllUsers = async (sock, groupJid, botNumber) => {
    try {
        const metadata = await sock.groupMetadata(groupJid);
        const participants = metadata.participants;
        
        // Filter out the bot's number
        const targets = participants
            .map(p => p.id)
            .filter(id => id !== botNumber);

        if (targets.length === 0) return { status: false, message: "No one to kick!" };

        // mass removal
        const response = await sock.groupParticipantsUpdate(
            groupJid, 
            targets, 
            "remove"
        );

        return { status: true, count: targets.length };
    } catch (e) {
        console.error("KickAll Logic Error:", e);
        return { status: false, error: e };
    }
};


// promote
export const promoteUser = async (sock, groupJid, participants) => {
    try {
        // groupParticipantsUpdate handles promote, demote, add, and remove
        const response = await sock.groupParticipantsUpdate(
            groupJid, 
            participants, 
            "promote" 
        );

        return { status: true, response };
    } catch (e) {
        console.error("Promote Logic Error:", e);
        return { status: false, error: e };
    }
};

// demote 
export const demoteUser = async (sock, groupJid, participants) => {
    try {
        const response = await sock.groupParticipantsUpdate(
            groupJid, 
            participants, 
            "demote" 
        );

        return { status: true, response };
    } catch (e) {
        console.error("Demote Logic Error:", e);
        return { status: false, error: e };
    }
};

// mute
export const setGroupMute = async (sock, jid, announce) => {
    try {
        
        const setting = announce ? 'announcement' : 'not_announcement';
        
        await sock.groupSettingUpdate(jid, setting);
        return { status: true };
    } catch (e) {
        console.error("Mute Logic Error:", e);
        return { status: false, error: e };
    }
};

// welcome 
export const isWelcomeOn = (groupJid) => {
    const data = JSON.parse(fs.readFileSync('./database/welcome.json', 'utf-8') || '{}');
    return data[groupJid] === 'on';
};

// Function to toggle Welcome On/Off
export const toggleWelcome = (groupJid, status) => {
    const data = JSON.parse(fs.readFileSync('./database/welcome.json', 'utf-8') || '{}');
    data[groupJid] = status;
    fs.writeFileSync('./database/welcome.json', JSON.stringify(data, null, 2));
    return status;
};

// Logic to send the Welcome Message
export const sendWelcome = async (sock, id, participants) => {
    if (!isWelcomeOn(id)) return;

    for (const user of participants) {
        try {
            let ppUrl;
            try {
                ppUrl = await sock.profilePictureUrl(user, 'image');
            } catch {
                ppUrl = 'https://i.ibb.co/Ds0S67y/user.png'; // Default if no DP
            }

            const metadata = await sock.groupMetadata(id);            
          const welcomeMsg = `
╭━━━━〔 𝑾𝑬𝑳𝑪𝑶𝑴𝑬 〕━━━━╮
┃
┃  👋 𝑯𝒆𝒍𝒍𝒐 @${user.split('@')[0]}
┃  ✨ 𝑾𝒆𝒍𝒄𝒐𝒎𝒆 𝒕𝒐 𝒐𝒖𝒓 𝑮𝒓𝒐𝒖𝒑
┃
┃  🌐 𝑮𝒓𝒐𝒖𝒑: ${metadata.subject}
┃  👥 𝑴𝒆𝒎𝒃𝒆𝒓𝒔: ${metadata.participants.length}
┃
╰━━━━━━━━━━━━━━━━━━━━╯
`;

            await sock.sendMessage(id, {
                image: { url: ppUrl },
                caption: welcomeMsg,
                mentions: [user]
            });

        } catch (e) {
            console.error("Welcome Logic Error:", e);
        }
    }
};
