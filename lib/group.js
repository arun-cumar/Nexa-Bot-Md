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

