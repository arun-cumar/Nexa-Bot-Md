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
