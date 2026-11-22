// Renders demo/match.html frame by frame. Usage: node demo/render_match.js <frames dir> <seconds> [fps=25] [only t]
const { chromium } = require("playwright"); const path = require("path");
(async () => {
  const [dir, secs, fps = 25, only] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  await p.goto("file://" + path.resolve(__dirname, "match.html"), { waitUntil: "networkidle" }); await p.evaluate(() => document.fonts.ready);
  const ts = only !== undefined ? [Number(only)] : Array.from({ length: Math.ceil(secs * fps) }, (_, i) => i / fps);
  for (let i = 0; i < ts.length; i++) {
    await p.evaluate((t) => window.render(t), ts[i]);
    const f = only !== undefined ? `still_${only}.png` : `f${String(i).padStart(5, "0")}.jpg`;
    await p.screenshot(f.endsWith("png") ? { path: path.join(dir, f) } : { path: path.join(dir, f), type: "jpeg", quality: 90 });
  }
  await b.close();
})();
