// © 2026 arun•°Cumar. All Rights Reserved.
import { fquoted } from './settings/quoted.js';
import menuHandler from '../commands/menu.js';
import aliveHandler from '../commands/alive.js';
import pingHandler from '../commands/ping.js';
import urlHandler from '../commands/url.js';

export default async (commandName, sock, msg, args, extra) => {
    const { isOwner, isAdmin } = extra;

    if (commandName === 'menu' || commandName === 'help') {
        await menuHandler(sock, msg, args);
    } 
    
    else if (commandName === 'alive') {
        await aliveHandler(sock, msg, fquoted);
    }
    
     else if (commandName === 'ping') {
        await pingHandler(sock, msg, fquoted);
    }
     
     else if (commandName === 'url') {
        await urlHandler(sock, msg, fquoted);
    }
        
        console.log(`Unknown command: ${commandName}`);
    }
};
