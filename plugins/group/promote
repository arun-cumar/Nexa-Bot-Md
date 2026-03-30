import { promoteUser } from '../../lib/group.js';

export default {
    name: 'promote',
    category: 'group',
    description: 'Promotes a mentioned or replied user to admin',
    async execute(sock, msg, args) {
        const groupJid = msg.key.remoteJid;

        // Ensure it is a group
        if (!groupJid.endsWith('@g.us')) {
            return sock.sendMessage(groupJid, { text: 'This command is for groups only!' }, { quoted: msg });
        }

        // Identify the user to promote
        let targets = [];
        const quoted = msg.message?.extendedTextMessage?.contextInfo;
        
        if (quoted?.participant) {
            targets = [quoted.participant]; // From reply
        } else if (quoted?.mentionedJid?.length > 0) {
            targets = quoted.mentionedJid; // From mentions
        }

        if (targets.length === 0) {
            return sock.sendMessage(groupJid, { text: 'Please reply to a message or tag someone to promote.' }, { quoted: msg });
        }

        // Execute the promote logic
        const result = await promoteUser(sock, groupJid, targets);

        if (result.status) {
            await sock.sendMessage(groupJid, { text: 'User(s) promoted to admin successfully! 👑' }, { quoted: msg });
        } else {
            await sock.sendMessage(groupJid, { text: 'Failed to promote. Ensure the bot is an admin!' }, { quoted: msg });
        }
    }
};
