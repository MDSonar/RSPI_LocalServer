# 📖 RSPI LocalServer – Documentation Index

Welcome! Here's how to navigate the RSPI LocalServer project.

## 🚀 Start Here

**New to the project?** Start with one of these:

### For the Impatient 
**→ [QUICKSTART.md](QUICKSTART.md)** (5 minutes)
- 30-second installation one-liner
- Basic commands
- Common setup issues

### For Detailed Setup
**→ [DEPLOYMENT.md](DEPLOYMENT.md)** (30 minutes)
- Step-by-step checklist
- USB drive setup (auto-mount or manual)
- Feature testing
- Troubleshooting matrix
- Security checklist

### For Everything
**→ [README.md](README.md)** (reference)
- Features overview
- Installation guide
- Configuration reference
- API endpoints
- Security notes
- Performance characteristics
- FAQ

---

## 📚 Full Documentation Map

| Document | Best For | Time | Key Topics |
|----------|----------|------|-----------|
| **[BUILD_SUMMARY.md](BUILD_SUMMARY.md)** | Project overview | 10 min | What you got, quick start, essential commands |
| **[QUICKSTART.md](QUICKSTART.md)** | Fast setup | 5 min | Installation, basic commands, USB mounting |
| **[DEPLOYMENT.md](DEPLOYMENT.md)** | Step-by-step | 30 min | Pre-flight, OS setup, install, verify, maintain |
| **[README.md](README.md)** | Complete reference | 30 min | All features, config, API, troubleshooting, FAQ |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Technical deep dive | 20 min | Design, modules, security, performance, extensibility |
| **[PROJECT_CONTENTS.md](PROJECT_CONTENTS.md)** | File inventory | 10 min | What's in each file, structure, dependencies |

---

## 🎯 Documentation by Use Case

### "I just want to set it up"
1. Read: [QUICKSTART.md](QUICKSTART.md)
2. Run: `sudo bash install.sh`
3. Access: `http://<pi-ip>:8080`
4. Done!

### "I want to do a proper deployment"
1. Read: [DEPLOYMENT.md](DEPLOYMENT.md) – section by section
2. Follow the checklist exactly
3. Test each step
4. Go live with confidence

### "I need to understand how it works"
1. Read: [ARCHITECTURE.md](ARCHITECTURE.md)
2. Review: [PROJECT_CONTENTS.md](PROJECT_CONTENTS.md) – module by module
3. Skim code: `app/main.py` → `app/file_manager.py` → `app/static/index.html`

### "I want to customize or extend it"
1. Start: [ARCHITECTURE.md](ARCHITECTURE.md) – "Extension Points" section
2. Modify: Code in `app/` folder
3. Test: `python3 app/main.py` (dev server)
4. Deploy: `sudo bash update.sh`

### "Something is broken"
1. Check: [README.md](README.md) – Troubleshooting section
2. View logs: `sudo journalctl -u rspi-localserver -f`
3. Check: [DEPLOYMENT.md](DEPLOYMENT.md) – Troubleshooting matrix

### "I need to update or uninstall"
1. Update: `cd ~/RSPI_LocalServer && sudo bash update.sh`
2. Uninstall: `cd ~/RSPI_LocalServer && sudo bash uninstall.sh`
3. Reinstall: `sudo bash install.sh`

---

## 🔍 Quick Reference

### Essential Commands
```bash
# Check status
sudo systemctl status rspi-localserver

# View logs (real-time)
sudo journalctl -u rspi-localserver -f

# Edit config
sudo nano /etc/rspi-localserver/config.yaml
sudo systemctl restart rspi-localserver

# Update
cd ~/RSPI_LocalServer && sudo bash update.sh

# Uninstall
cd ~/RSPI_LocalServer && sudo bash uninstall.sh
```

### Key Directories
```
/opt/rspi-localserver/     # App code & venv
/etc/rspi-localserver/     # Config file
/var/log/rspi-localserver/ # Logs
/media/usb/                # Your file storage
```

### Key Files
```
app/main.py           # FastAPI routes
app/file_manager.py   # File operations + security
app/static/index.html # Web UI
config/config.yaml    # Default config
install.sh            # Installation
update.sh             # Update with rollback
uninstall.sh          # Uninstall
```

---

## 🏗️ Project Structure

```
RSPI_LocalServer/
├── 📖 Documentation
│   ├── README.md                    ← Full reference (start here for details)
│   ├── QUICKSTART.md                ← Fast setup (30 seconds)
│   ├── DEPLOYMENT.md                ← Step-by-step checklist
│   ├── ARCHITECTURE.md              ← Technical design & security
│   ├── PROJECT_CONTENTS.md          ← File inventory
│   ├── BUILD_SUMMARY.md             ← Project overview
│   └── INDEX.md                     ← This file
│
├── 🐍 Application Code
│   ├── app/
│   │   ├── main.py                  (FastAPI routes)
│   │   ├── config.py                (configuration)
│   │   ├── file_manager.py          (file ops + security)
│   │   ├── __init__.py              (package marker)
│   │   └── static/
│   │       └── index.html           (web UI)
│   ├── config/
│   │   └── config.yaml              (default config)
│   ├── requirements.txt             (Python packages)
│   └── .gitignore                   (git ignore)
│
└── 🔧 Deployment Scripts
    ├── install.sh                   (installation)
    ├── update.sh                    (update with backup)
    └── uninstall.sh                 (uninstall)
```

---

## 📊 Documentation Stats

| Document | Length | Purpose |
|----------|--------|---------|
| README.md | 500 lines | Complete reference |
| DEPLOYMENT.md | 400 lines | Checklist-based setup |
| ARCHITECTURE.md | 600 lines | Technical design |
| PROJECT_CONTENTS.md | 400 lines | File inventory |
| QUICKSTART.md | 100 lines | Ultra-fast setup |
| BUILD_SUMMARY.md | 300 lines | Project overview |
| **Total** | **~2,300 lines** | Comprehensive |

---

## 🎓 Learning Path

### Beginner (Just want it running)
```
QUICKSTART.md
    ↓
install.sh
    ↓
http://<pi-ip>:8080 ✅
```

### Intermediate (Understand the setup)
```
BUILD_SUMMARY.md
    ↓
DEPLOYMENT.md
    ↓
README.md (config section)
    ↓
Fully deployed & configured ✅
```

### Advanced (Understand & modify)
```
ARCHITECTURE.md
    ↓
PROJECT_CONTENTS.md
    ↓
Read source code:
  app/main.py
  app/file_manager.py
  app/static/index.html
    ↓
Extend or customize ✅
```

### Expert (Build from scratch understanding)
```
ARCHITECTURE.md (full)
    ↓
PROJECT_CONTENTS.md (full)
    ↓
Read all source code
    ↓
Modify & contribute ✅
```

---

## 🔐 Security Docs

**Security-focused?** Check:
- [README.md](README.md#security-notes) – Security section
- [ARCHITECTURE.md](ARCHITECTURE.md#security-model) – Threat model & defenses
- [DEPLOYMENT.md](DEPLOYMENT.md#security-checklist) – Security checklist

---

## 🆘 Finding Answers

**"How do I...?"**

| Question | Answer |
|----------|--------|
| Set it up quickly? | [QUICKSTART.md](QUICKSTART.md) |
| Deploy step-by-step? | [DEPLOYMENT.md](DEPLOYMENT.md) |
| Configure the app? | [README.md](README.md#configuration) |
| Use the API? | [README.md](README.md#api-endpoints) |
| Fix a problem? | [README.md](README.md#troubleshooting) |
| Understand design? | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Find a specific file? | [PROJECT_CONTENTS.md](PROJECT_CONTENTS.md) |
| See quick commands? | [BUILD_SUMMARY.md](BUILD_SUMMARY.md#-essential-commands) |

---

## 💡 Tips

1. **Always start with [QUICKSTART.md](QUICKSTART.md)** – Gets you going in 5 minutes
2. **Use [DEPLOYMENT.md](DEPLOYMENT.md) as a checklist** – Ensures nothing is missed
3. **Bookmark [README.md](README.md)** – Your go-to reference
4. **Read [ARCHITECTURE.md](ARCHITECTURE.md) before customizing** – Understand design first
5. **Keep logs handy:** `sudo journalctl -u rspi-localserver -f`

---

## 📞 Quick Links

### Installation
- [QUICKSTART.md](QUICKSTART.md) – Ultra-fast setup (5 min)
- [DEPLOYMENT.md](DEPLOYMENT.md) – Detailed checklist (30 min)

### Configuration & Reference
- [README.md](README.md) – Complete manual
- [config/config.yaml](config/config.yaml) – Default settings

### Code & Architecture
- [ARCHITECTURE.md](ARCHITECTURE.md) – Design & security
- [PROJECT_CONTENTS.md](PROJECT_CONTENTS.md) – File inventory
- [app/](app/) – Source code

### Deployment
- [install.sh](install.sh) – Automated install
- [update.sh](update.sh) – Update with rollback
- [uninstall.sh](uninstall.sh) – Safe uninstall

---

## 🎯 The 30-Second Version

```bash
# On Raspberry Pi 4B running Raspberry Pi OS Lite:
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
sudo mkdir -p /media/usb
sudo mount /dev/sda1 /media/usb/mydrive  # Mount your USB drive

cd ~/RSPI_LocalServer
sudo bash install.sh

# Access at: http://<your-pi-ip>:8080
```

Full guide: [QUICKSTART.md](QUICKSTART.md)  
Detailed guide: [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 📝 Document Overview

### README.md
**The master reference.** Covers everything: features, install, config, API, troubleshooting, FAQ.

### QUICKSTART.md
**Get up and running in 5 minutes.** Ultra-concise; assumes you know Linux basics.

### DEPLOYMENT.md
**Detailed step-by-step checklist.** Perfect for methodical deployment; includes pre-flight, testing, verification.

### ARCHITECTURE.md
**Technical deep dive.** For developers: design rationale, module breakdown, security model, performance, extensibility.

### PROJECT_CONTENTS.md
**File inventory & reference.** Lists every file, its purpose, key functions, and dependencies.

### BUILD_SUMMARY.md
**Project overview.** Quick summary of what you got, how to use it, essential commands, tips.

### INDEX.md (This file)
**Navigation guide.** Helps you find the right document for your needs.

---

## ✅ You're Ready!

Pick your starting document and dive in:

👉 **In a hurry?** → [QUICKSTART.md](QUICKSTART.md)

👉 **Want to do it right?** → [DEPLOYMENT.md](DEPLOYMENT.md)

👉 **Need complete reference?** → [README.md](README.md)

👉 **Want to understand design?** → [ARCHITECTURE.md](ARCHITECTURE.md)

👉 **Looking for something specific?** → This index!

---

**Happy file sharing!** 🚀

Built for Raspberry Pi 4B with love (and minimal RAM).
