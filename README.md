# CampusAlert (SDSU prototype)
Plain HTML + CSS + JavaScript. No install needed.

- `index.html` – all screens
- `style.css` – look & colors
- `app.js` – logic (SOS hold, call, reports, GPS, text message)

Help number (SOS call + live location text): 605-691-3414 — change `HELP_NUMBER` in app.js.

## Run locally
Double-click index.html, or: `python -m http.server 8000` then open http://localhost:8000

## Host free on GitHub Pages
1. Create a new public repo on github.com, upload these files.
2. Settings → Pages → Source: "Deploy from a branch" → main / root → Save.
3. Your live link: https://YOUR-USERNAME.github.io/REPO-NAME/
(GPS needs https, which GitHub Pages gives you. Calls/texts open the dialer on a phone.)
