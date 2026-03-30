import { setAntilinkStatus } from '../lib/group.js';

export default {
    name: 'antilink',
    category: 'group',
    description: 'Turn antilink on or off',
    async execute(sock, msg, args) {
        const groupJid = msg.key.remoteJid;

        if (!groupJid.endsWith('@g.us')) {
            return sock.sendMessage(groupJid, { text: 'This command only works in groups!' });
        }

        const action = args[0]?.toLowerCase();

        if (action === 'on') {
            setAntilinkStatus(groupJid, 'on');
            return sock.sendMessage(groupJid, { text: '✅ *Antilink is now ON* for this group.' });
        }

        if (action === 'off') {
            setAntilinkStatus(groupJid, 'off');
            return sock.sendMessage(groupJid, { text: '❌ *Antilink is now OFF*.' });
        }

        return sock.sendMessage(groupJid, { 
            text: 'Usage: *.antilink on* or *.antilink off*' 
        });
    }
};
