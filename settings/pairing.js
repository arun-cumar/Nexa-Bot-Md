export async function handlePairing(sock) {
     if (!sock.authState.creds.registered) {
        const phoneNumber = await question('\n📞Enter your Phone Number with Country Code (eg: 91xxxx): ');
        const code = await sock.requestPairingCode(phoneNumber.replace(/[^0-9]/g, ''));
        console.log(`\x1b[32m\nYOUR 🗝 PAIRING CODE: \x1b[1m${code}\x1b[0m\n`);
    }


