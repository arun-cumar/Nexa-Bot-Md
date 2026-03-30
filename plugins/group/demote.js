import { demoteUser } from '../../lib/group.js';

export default {
    name: 'demote',
    category: 'group',
    description: 'Removes admin status from a user',
    async execute(sock, msg, args) {
        const groupJid = msg.key.remoteJid;

        // Group check
        if (!groupJid.endsWith('@g.us')) {
            return sock.sendMessage(groupJid, { text: 'Group only command!' }, { quoted: msg });
        }

        // Identify target (Reply or Mention)
        let target;
        const contextInfo = msg.message?.extendedTextMessage?.contextInfo;

        if (contextInfo?.participant) {
            target = [contextInfo.participant];
        } else if (contextInfo?.mentionedJid?.length > 0) {
            target = contextInfo.mentionedJid;
        }

        if (!target || target.length === 0) {
            return sock.sendMessage(groupJid, { text: 'Tag or reply to the admin you want to demote.' }, { quoted: msg });
        }

        // Call logic
        const result = await demoteUser(sock, groupJid, target);

        if (result.status) {
            await sock.sendMessage(groupJid, { text: 'Admin powers removed. 📉' }, { quoted: msg });
        } else {
            await sock.sendMessage(groupJid, { text: 'Error! Am I an admin? Is the target an admin?' }, { quoted: msg });
        }
    }
};
