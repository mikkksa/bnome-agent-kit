// Tiny interactive prompt helpers (no deps). Password input is masked.
import readline from "node:readline";

export function ask(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => rl.question(question, (a) => { rl.close(); resolve(a.trim()); }));
}

// Read a line without echoing keystrokes (for passwords).
export function askHidden(question) {
  return new Promise((resolve) => {
    process.stdout.write(question);
    const stdin = process.stdin;
    const wasRaw = stdin.isRaw;
    stdin.setRawMode?.(true);
    stdin.resume();
    stdin.setEncoding("utf8");
    let buf = "";
    const onData = (ch) => {
      switch (ch) {
        case "\n": case "\r": case "\u0004": // enter / EOT
          stdin.setRawMode?.(wasRaw);
          stdin.pause();
          stdin.removeListener("data", onData);
          process.stdout.write("\n");
          resolve(buf);
          break;
        case "\u0003": // Ctrl-C
          process.stdout.write("\n");
          process.exit(1);
          break;
        case "\u007f": case "\b": // backspace
          if (buf.length) { buf = buf.slice(0, -1); process.stdout.write("\b \b"); }
          break;
        default:
          buf += ch;
          process.stdout.write("*");
      }
    };
    stdin.on("data", onData);
  });
}
