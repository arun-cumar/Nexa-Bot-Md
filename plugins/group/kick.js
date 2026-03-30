import { kickUser } from '../../lib/message.js';
export default {
    name: 'kick',
    category: 'group',
    description: 'Kicks a mentioned user or replied user',
    async execute(sock, msg, args) {
        const groupJid = msg.key.remoteJid;

        // Check if it's a group
        if (!groupJid.endsWith('@g.us')) {
            return sock.sendMessage(groupJid, { text: 'This command only works in groups!' }, { quoted: msg });
        }

        // Get the user to kick (from reply or mention)
        let victim;
        if (msg.message?.extendedTextMessage?.contextInfo?.participant) {
            victim = [msg.message.extendedTextMessage.contextInfo.participant];
        } else if (msg.message?.extendedTextMessage?.contextInfo?.mentionedJid?.length > 0) {
            victim = msg.message.extendedTextMessage.contextInfo.mentionedJid;
        }

        if (!victim || victim.length === 0) {
            return sock.sendMessage(groupJid, { text: 'Please reply to a message or tag someone to kick.' }, { quoted: msg });
        }

        const result = await kickUser(sock, msg, victim);

        if (result.status) {
            await sock.sendMessage(groupJid, { text: 'Target removed successfully. 😤' }, { quoted: msg });
        } else {
            await sock.sendMessage(groupJid, { text: 'Failed to kick. Make sure I am an admin!' }, { quoted: msg });
        }
    }
};
