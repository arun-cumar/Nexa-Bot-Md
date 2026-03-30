import { setGroupMute } from '../../lib/group.js';

export default {
    name: 'mute',
    category: 'group',
    description: 'Mute or Unmute the group chat',
    async execute(sock, msg, args) {
        const groupJid = msg.key.remoteJid;

        // Ensure it is a group
        if (!groupJid.endsWith('@g.us')) {
            return sock.sendMessage(groupJid, { text: 'This command only works in groups!' }, { quoted: msg });
        }

        const action = args[0] ? args[0].toLowerCase() : '';

        if (action === 'on' || action === 'close') {
            const result = await setGroupMute(sock, groupJid, true);
            if (result.status) {
                await sock.sendMessage(groupJid, { text: 'Group Closed. Only admins can send messages. 🔒' });
            } else {
                await sock.sendMessage(groupJid, { text: 'Failed to mute. Check bot permissions.' });
            }
        } 
        else if (action === 'off' || action === 'open') {
            const result = await setGroupMute(sock, groupJid, false);
            if (result.status) {
                await sock.sendMessage(groupJid, { text: 'Group Opened. Everyone can send messages. 🔓' });
            } else {
                await sock.sendMessage(groupJid, { text: 'Failed to unmute. Check bot permissions.' });
            }
        } 
        else {
            await sock.sendMessage(groupJid, { text: 'Usage: !mute on / !mute off' }, { quoted: msg });
        }
    }
};
