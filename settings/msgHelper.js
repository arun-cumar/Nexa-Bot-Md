import config from "../config.js";

export const parseMessage = (msg) => {

    const m = msg.message || {};

    const body =
        m.conversation ||
        m.extendedTextMessage?.text ||
        m.imageMessage?.caption ||
        m.videoMessage?.caption ||
        m.documentMessage?.caption ||
        m.buttonsResponseMessage?.selectedButtonId ||
        m.listResponseMessage?.singleSelectReply?.selectedRowId ||
        m.templateButtonReplyMessage?.selectedId ||
        m.interactiveResponseMessage?.nativeFlowResponseMessage?.paramsJson ||
        m.viewOnceMessage?.message?.imageMessage?.caption ||
        m.viewOnceMessage?.message?.videoMessage?.caption ||
        "";

    const text = body.trim();
    
    const isCmd = config.PREFIX.split('').some(p => text.startsWith(p));
    const prefix = isCmd ? config.PREFIX.split('').find(p => text.startsWith(p)) : "";

    const commandName = isCmd
        ? text.slice(prefix.length).trim().split(/ +/)[0].toLowerCase()
        : "";

    const args = isCmd ? text.trim().split(/ +/).slice(1) : [];

    const from = msg.key?.remoteJid;
    const isGroup = from?.endsWith("@g.us");
    const sender = isGroup ? msg.key?.participant : from;

    return {
        body,
        text,
        isCmd,
        commandName,
        args,
        sender,
        from,
        isGroup,
        prefix,
        msg
    };
};
