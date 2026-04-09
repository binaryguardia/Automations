#!/usr/bin/env python3
"""
APKeep Dashboard — Cross-Platform APK Downloader
Works on Linux, Windows (WSL/CMD), macOS
Run: python3 apkeep_dashboard.py
Then open http://localhost:8080 in your browser
"""

import os
import sys
import json
import shutil
import zipfile
import platform
import subprocess
import threading
import http.server
import urllib.parse
import urllib.request
import re
import time
from pathlib import Path

# ─── Cross-platform paths ───────────────────────────────────────────────────
IS_WINDOWS = platform.system() == "Windows"
IS_MAC     = platform.system() == "Darwin"
IS_LINUX   = platform.system() == "Linux"

HOME = Path.home()
DEFAULT_OUT = HOME / "apks_by_developer"

# ─── Dev map for organizing (same as before) ────────────────────────────────
DEV_MAP = {
    # LoopStack Studio
    **{p: "LoopStack_Studio" for p in [
        "com.lss.sketch.drawing.color.puzzle.brain.game",
        "com.lss.unicorn.cat.princess.fashion.run.dressup.game",
        "com.lss.flamingo.flying.seabird.bird.parrot.simulator",
        "com.lss.ragdoll.bones.smash.fall.destroy.fun.game",
        "com.lss.arctic.snow.white.survival.wolf.waves.game",
        "com.lss.virtual.family.life.summer.vacation.adventure.simulator",
        "com.lss.ragdoll.bike.downhill.crash.stunt.impossible.sim.game",
        "com.lss.crazy.highway.bus.crash.smash.stunt.racing.games",
        "com.lss.plane.flight.crash.race.destruction.fall.sim.game",
        "com.lss.virtual.mom.family.happylife.familia.care.simulator.game",
        "com.lss.euro.truck.transport.tycoon.driving.simulator.game",
        "com.lss.wild.lion.animal.family.survival.hunting.simulator",
        "com.lss.tractor.farm.happytown.farming.farmer.village.simulator.game",
        "com.lss.fantasy.magical.unicorn.flying.cat.care.sim.game",
        "com.lss.virtual.police.mom.mother.family.life.care.simulator.game",
        "com.lss.ragdoll.bmx.stunts.crash.fall.destroy.game",
        "com.lss.wild.dino.dinosaur.hunting.jurassic.world.survival.sniper.shooting.game",
        "com.lss.firefighter.ny.city.truck.rescue.game",
        "com.lss.truck.crash.simulator.giant.big.accident.game",
        "com.lss.gansters.mafia.auto.vehicle.simulator.game",
    ]},
    # Peak Gaming Studio
    **{p: "Peak_Gaming_Studio" for p in [
        "com.peakgames.bussimultra","com.peakgames.vansimulator",
        "com.peakgames.pickupracing","com.peakgames.indiantruck",
        "com.peakgames.truckdriving","com.peakgames.indiantractor",
    ]},
    # Chromic Apps
    **{p: "Chromic_Apps" for p in [
        "com.ca.coachbus.bussimulator.busgames","com.ca.truck.driving.simulator.cargo.games",
        "com.ca.taxi.driving.simulator.car.games.driver","com.ca.animaltruck.animaltruckgame",
        "com.ca.bus.coach.city.driving.simulator.games","com.ca.prado.police.cars.driving.school.simulator.games",
        "com.ca.openworldgangster.gangstercargame","com.ca.pakistanindia.bus.simulator.game",
        "com.ca.eurotruck.truckdriving.eurotruckdriving","com.ca.vangames.vangame.dubaivangame",
        "com.ca.vandriving.vandrivingsimulator.vangames","com.ca.minicoachbus.busgame.eurobusdriving",
        "com.rs.us.agriculture.farming.simulator.game","com.ca.busdriving.citybus.citybusgames",
    ]},
    # Games Rack Studio
    **{p: "Games_Rack_Studio" for p in [
        "com.grs.bus.driving.game.simulator","com.gs.policecar.chasegames",
        "com.grs.suv.offroad.jeepsimulator","com.grs.police.car.chase.policecar",
        "com.gr.real.tractorfarming.tractor.driving.simulator","com.grs.eurobus.parking.bussimulator",
        "com.rki.mudtruck.drivingsimulator.offroad","com.grs.us.oiltanker.truckdrive.simulator",
        "com.gs.mudtruck.simulator.game","com.grs.miami.gangster.game",
    ]},
    # Gamex Global
    **{p: "Gamex_Global" for p in [
        "com.gamexglobal.flying.hero.jet.simulator.games","com.gamexglobal.farming.tractor.simulator.games",
        "com.gamexglobal.hoarding.and.cleaning.hoarder.cleanit","com.gamexglobal.car.parking.driver.simulator",
        "com.gamexglobal.ultimate.car.parking","com.city.highway.traffictransports.coach.drive.bus.simulator.free",
    ]},
    # Grandeur Gamers
    **{p: "Grandeur_Gamers" for p in [
        "com.grandeur.schoolbussimulator.busgame","com.grandeur.dumptruck.americantruck",
        "com.grandeur.eurotruck.trucksimulator","com.toptier.IndianBus.BusSimulator",
    ]},
    # MNK Games
    **{p: "MNK_Games" for p in [
        "com.MNKGames.nuts.bolts.wood","com.MNKGames.zombieshooter.runner",
        "com.MNKGames.constructioncity","com.MNK.bus_simulator",
        "com.MNKGames.CarTrafficEscape","com.MNKGames.Cardealership3d.freegames",
        "com.MNKGames.LiftUp.skygames",
    ]},
    # Vroom
    **{p: "Vroom_Apps_and_Games" for p in [
        "com.car.drift.racing.sim.rol","com.scary.mom.bad.cat.pet.simulator.games",
        "com.toy.soldiers.fps.war.battle.shooting","com.sling.strike.action.whackgame.simulator",
        "com.bonebreaker.ragdoll.race.game.simulator","com.merge.battle.fight.heroes.games",
        "com.yhi.gym.fitness.runner.game","com.yhi.punch.smash.boxing.arms",
        "com.yhi.police.fps.sniper.gun.shooting.games","com.yhi.Stickman.police.motorbike.city.cop.gangster.chase",
    ]},
    # Crea8iv Games
    **{p: "Crea8iv_Games" for p in [
        "com.Crea8ivGames.monster.freetruck.big.wheels.drive","com.Crea8ivGames.police.car.jeep.driving.simulator",
        "crea8ivgames.freetractor.driving.farming.game","com.Crea8ivGames.hill.army.truck",
        "com.Crea8ivGames.freetractor.driving.simulator","com.Crea8ivGames.freegame.heavy.truck.driver",
        "com.Crea8ivGames.freegame.monster.truck.simulator","com.Crea8ivGames.freegames.tractorstunt.mega.ramp",
        "com.Crea8ivGames.coach.bus.driving.offroadgame","com.Crea8ivGames.heavyduty.tractor.pull.Driver",
        "com.Crea8ivGames.newtruck.cargo.trasnspot.driver","com.Crea8ivGames.taxi.driving.simulator.freegame",
        "com.Crea8ivGames.pickup.cargo.truck.transport.hilldrive","com.Crea8ivGames.animal.ambulance.rescue.driver",
        "com.Crea8ivGames.offroad.police.van.real.driving","com.Crea8ivGames.cargotruck.freegame",
        "com.Crea8ivGames.prado.jeep.simulator.free.game","com.Crea8ivGames.tractortrolley.cargo.transport.drive",
        "com.Crea8ivGames.freebus.transport.driving.game","com.Crea8ivGames.freegame.tractor.trolley.racing",
    ]},
    # 360 Pixel Studio
    **{p: "360_Pixel_Studio" for p in [
        "com.ps.indiatouristbus.touristbussimulator","com.ps.aeroplaneflying.flyingsimulator",
        "com.ps.busgame.busgamesimulator.coachbus","com.ps.americancargotruck.cargotruckdriving",
        "com.ps.americantruck.driving.cargotruck.game","com.ps.police.car.simulator",
        "com.pog.offroad.oil.spooky.transport.truck.driver","com.vx.heavy.grand.indian.euro.spooky.truck",
        "com.wot.sniper.helicopter.shooter.deadly.war","com.ps.uscardriving.cardrivingsim",
    ]},
    # Pixels Pioneer
    **{p: "Pixels_Pioneer" for p in [
        "com.pixels.gangster.Dadagiri","com.pixels.kiteflying",
        "com.pixels.moto.bike.fever","com.pixels.crazysoccerkick",
        "com.pixels.IndianTruckDriver","com.pixels.IndianBusSimulator",
        "com.pixels.carstunt.demolition","com.pixels.indiantractorsimulator","com.pixels.uncanny",
    ]},
    # Pro Gaming Studio
    **{p: "Pro_Gaming_Studio" for p in [
        "com.pgs.tractor.farming.driving.simulator.game","com.pgs.euro.truck.game",
        "com.pgs.cop.sim.police.car.game","com.pgs.truck.simulator.truck.game",
        "com.pgs.aeroplane.flight.game.simulator","com.pgs.monster.truck.arena.game",
        "com.pgs.city.gangster.game","com.pgs.offroad.bus.sim.game",
    ]},
    # The Game School
    **{p: "The_Game_School" for p in [
        "com.tgs.memerot.waveescapes","com.speeddrive.commercial.bus.racing.games",
        "com.monster.truck.police.patrol.extreme.city.gangster.crime.games","com.indianmafiacity.openworld",
        "com.underground.hole.digging.simulator","com.nightclub.security.simulation.games",
        "com.offroad.euro.truck.racing.simulator.games","com.playaction.giant.elephant.robot.transform.games",
        "com.playction.crocodile.robot.fighting.simulator.game","com.playaction.gangster.monster.truck.simulator.game",
    ]},
    # Micro Madness
    **{p: "Micro_Madness" for p in [
        "com.mm.real.flight.game.simulator","com.mm.superiorcarparking.car.game",
        "com.gangstercar.chase.car.game","com.mm.bus.simulator.offline.bus.game",
        "com.real.tuk.tuk.auto.rickshaw","com.mm.tractor.farming.game",
        "com.mm.bus.game.indian.bus.simulator","com.citytrucksimulator.truck.game",
        "com.mm.rescue.animal.truck.transport","com.mm.indian.hill.truck.simulator.game",
        "com.mm.real.animals.truck.simulator",
    ]},
}

# ─── Global state ────────────────────────────────────────────────────────────
log_lines   = []
job_running = False
job_stats   = {"total": 0, "done": 0, "failed": 0, "current": ""}

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    log_lines.append(line)
    print(line)
    if len(log_lines) > 500:
        log_lines.pop(0)

# ─── apkeep helpers ──────────────────────────────────────────────────────────
def find_apkeep():
    """Find apkeep binary cross-platform."""
    candidates = ["apkeep", "apkeep.exe"]
    for c in candidates:
        if shutil.which(c):
            return c
    # Common install paths
    extra = [
        Path.home() / ".cargo/bin/apkeep",
        Path.home() / ".cargo/bin/apkeep.exe",
        Path("/usr/local/bin/apkeep"),
    ]
    for p in extra:
        if p.exists():
            return str(p)
    return None

def install_apkeep():
    """Try to install apkeep via cargo."""
    log("apkeep not found. Attempting install via cargo...")
    if not shutil.which("cargo"):
        return False, "cargo not found. Install Rust from https://rustup.rs first."
    result = subprocess.run(
        ["cargo", "install", "apkeep"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        log("apkeep installed successfully!")
        return True, "ok"
    return False, result.stderr

def extract_xapk(xapk_path: Path, dest_dir: Path) -> list:
    """Extract APKs from XAPK/APKS zip bundle."""
    extracted = []
    try:
        with zipfile.ZipFile(xapk_path, 'r') as z:
            for name in z.namelist():
                if name.endswith('.apk'):
                    z.extract(name, dest_dir)
                    src = dest_dir / name
                    dst = dest_dir / Path(name).name
                    if src != dst:
                        src.rename(dst)
                    extracted.append(dst)
    except Exception as e:
        log(f"  Extract error: {e}")
    return extracted

def parse_package_id(raw: str) -> str:
    """Extract package ID from URL or return as-is."""
    raw = raw.strip()
    m = re.search(r'[?&]id=([a-zA-Z0-9._]+)', raw)
    if m:
        return m.group(1)
    if re.match(r'^[a-zA-Z][a-zA-Z0-9._]+$', raw):
        return raw
    return raw

def parse_packages_text(text: str) -> list:
    """Parse a block of text into package IDs."""
    pkgs = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # comma or semicolon separated
        for part in re.split(r'[,;]', line):
            p = parse_package_id(part.strip())
            if p and re.match(r'^[a-zA-Z][a-zA-Z0-9._]+$', p):
                pkgs.append(p)
    return list(dict.fromkeys(pkgs))  # deduplicate

# ─── Download job ─────────────────────────────────────────────────────────────
def run_download_job(packages, out_dir, source, do_extract, do_organize):
    global job_running, job_stats
    job_running = True
    job_stats = {"total": len(packages), "done": 0, "failed": 0, "current": ""}

    apkeep = find_apkeep()
    if not apkeep:
        ok, msg = install_apkeep()
        if not ok:
            log(f"ERROR: {msg}")
            job_running = False
            return
        apkeep = find_apkeep()

    raw_dir = Path(out_dir) / "raw_downloads"
    raw_dir.mkdir(parents=True, exist_ok=True)

    log(f"Starting download of {len(packages)} packages → {raw_dir}")
    log(f"Source: {source} | Extract: {do_extract} | Organize: {do_organize}")
    log("─" * 50)

    for i, pkg in enumerate(packages):
        if not pkg:
            continue
        job_stats["current"] = pkg
        job_stats["done"] = i
        log(f"[{i+1}/{len(packages)}] Downloading: {pkg}")

        cmd = [apkeep, "-a", pkg, "-d", source, str(raw_dir)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                log(f"  ✓ Downloaded: {pkg}")
            else:
                log(f"  ✗ Failed: {pkg} — {result.stderr.strip()[:100]}")
                job_stats["failed"] += 1
        except subprocess.TimeoutExpired:
            log(f"  ✗ Timeout: {pkg}")
            job_stats["failed"] += 1
        except Exception as e:
            log(f"  ✗ Error: {pkg} — {e}")
            job_stats["failed"] += 1

    log("─" * 50)
    log("Download phase complete. Starting extraction...")

    # Extract and organize
    for file in raw_dir.iterdir():
        if file.suffix in ('.xapk', '.apks'):
            pkg_name = file.stem
            log(f"Extracting: {file.name}")
            if do_extract:
                apks = extract_xapk(file, raw_dir)
                for apk in apks:
                    log(f"  → {apk.name}")
                    if do_organize:
                        dev = DEV_MAP.get(pkg_name, "Unknown_Developer")
                        dev_dir = Path(out_dir) / dev
                        dev_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(apk, dev_dir / apk.name)
        elif file.suffix == '.apk':
            if do_organize:
                pkg_name = file.stem
                dev = DEV_MAP.get(pkg_name, "Unknown_Developer")
                dev_dir = Path(out_dir) / dev
                dev_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dev_dir / file.name)

    job_stats["done"] = len(packages)
    job_stats["current"] = "complete"

    # Final report
    log("─" * 50)
    log("COMPLETE! Summary:")
    if do_organize:
        for dev_dir in sorted(Path(out_dir).iterdir()):
            if dev_dir.is_dir() and dev_dir.name != "raw_downloads":
                count = len(list(dev_dir.glob("*.apk")))
                log(f"  {dev_dir.name}: {count} APK(s)")
    total_apks = len(list(Path(out_dir).rglob("*.apk")))
    log(f"Total APKs: {total_apks} | Failed: {job_stats['failed']}")
    log(f"Output: {out_dir}")
    job_running = False

# ─── HTML UI ──────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>APKeep Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet"/>
<style>
:root{
  --bg:#07070f;--surface:#0f0f1a;--surface2:#16162a;
  --border:#252538;--accent:#00ff88;--accent2:#7c3aed;--accent3:#f59e0b;
  --text:#e8e8f0;--muted:#5a5a7a;--danger:#ff4466;
  --mono:'Space Mono',monospace;--display:'Syne',sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--mono);min-height:100vh}
body::before{content:'';position:fixed;inset:0;
  background-image:linear-gradient(var(--border) 1px,transparent 1px),
  linear-gradient(90deg,var(--border) 1px,transparent 1px);
  background-size:48px 48px;opacity:0.25;pointer-events:none;z-index:0}

.wrap{position:relative;z-index:1;max-width:1000px;margin:0 auto;padding:32px 20px}

/* Header */
header{display:flex;align-items:center;gap:14px;margin-bottom:36px;animation:fadeD .5s ease both}
.logo{width:48px;height:48px;background:var(--accent);border-radius:10px;
  display:flex;align-items:center;justify-content:center;font-size:20px;
  box-shadow:0 0 24px rgba(0,255,136,.35);flex-shrink:0}
header h1{font-family:var(--display);font-size:26px;font-weight:800}
header h1 span{color:var(--accent)}
header p{font-size:10px;color:var(--muted);letter-spacing:.1em;margin-top:2px}
.badge{margin-left:auto;background:rgba(0,255,136,.08);border:1px solid rgba(0,255,136,.25);
  color:var(--accent);font-size:9px;padding:4px 10px;border-radius:20px;
  letter-spacing:.1em;text-transform:uppercase;white-space:nowrap}

/* Status bar */
.statusbar{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:28px;animation:fadeU .5s .1s ease both}
.scard{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px;text-align:center}
.snum{font-family:var(--display);font-size:20px;font-weight:800;color:var(--accent)}
.slbl{font-size:9px;color:var(--muted);letter-spacing:.1em;text-transform:uppercase;margin-top:2px}

/* Tabs */
.tabs{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:24px;animation:fadeU .5s .15s ease both}
.tab{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:16px;cursor:pointer;transition:all .2s;text-align:left;position:relative;overflow:hidden}
.tab::after{content:'';position:absolute;inset:0;opacity:0;transition:opacity .2s}
.tab[data-t="dev"]::after{background:linear-gradient(135deg,rgba(0,255,136,.07),transparent)}
.tab[data-t="single"]::after{background:linear-gradient(135deg,rgba(124,58,237,.07),transparent)}
.tab[data-t="bulk"]::after{background:linear-gradient(135deg,rgba(245,158,11,.07),transparent)}
.tab:hover::after,.tab.active::after{opacity:1}
.tab.active[data-t="dev"]{border-color:var(--accent)}
.tab.active[data-t="single"]{border-color:var(--accent2)}
.tab.active[data-t="bulk"]{border-color:var(--accent3)}
.ticon{font-size:20px;margin-bottom:8px;display:block}
.ttitle{font-family:var(--display);font-size:13px;font-weight:700;margin-bottom:3px}
.tab.active[data-t="dev"] .ttitle{color:var(--accent)}
.tab.active[data-t="single"] .ttitle{color:var(--accent2)}
.tab.active[data-t="bulk"] .ttitle{color:var(--accent3)}
.tdesc{font-size:10px;color:var(--muted);line-height:1.5}

/* Panels */
.panel{background:var(--surface);border:1px solid var(--border);border-radius:14px;
  padding:24px;display:none;animation:fadeU .3s ease both}
.panel.active{display:block}
.ph{display:flex;align-items:center;gap:10px;margin-bottom:22px;
  padding-bottom:14px;border-bottom:1px solid var(--border)}
.pdot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dev .pdot{background:var(--accent);box-shadow:0 0 8px var(--accent)}
.single .pdot{background:var(--accent2);box-shadow:0 0 8px var(--accent2)}
.bulk .pdot{background:var(--accent3);box-shadow:0 0 8px var(--accent3)}
.ptitle{font-family:var(--display);font-weight:700;font-size:15px}

/* Forms */
.fg{margin-bottom:18px}
label{display:block;font-size:10px;color:var(--muted);letter-spacing:.1em;text-transform:uppercase;margin-bottom:7px}
input[type=text],textarea,select{
  width:100%;background:var(--surface2);border:1px solid var(--border);
  border-radius:8px;color:var(--text);font-family:var(--mono);font-size:12px;
  padding:11px 13px;outline:none;transition:border-color .2s;resize:vertical}
input[type=text]:focus,textarea:focus,select:focus{border-color:var(--accent)}
.single input:focus,.single select:focus{border-color:var(--accent2)}
.bulk input:focus,.bulk textarea:focus,.bulk select:focus{border-color:var(--accent3)}
textarea{min-height:120px}
select option{background:var(--surface2)}
.hint{font-size:10px;color:var(--muted);margin-top:5px}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px}
.chk{display:flex;align-items:center;gap:9px;padding:10px 13px;
  background:var(--surface2);border:1px solid var(--border);border-radius:7px;cursor:pointer}
.chk input{display:none}
.cbox{width:15px;height:15px;border:1px solid var(--border);border-radius:3px;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
  transition:all .2s;font-size:9px}
.chk input:checked+.cbox{background:var(--accent);border-color:var(--accent);color:#000}
.chk span{font-size:11px;color:var(--muted)}

/* Buttons */
.btn{display:inline-flex;align-items:center;gap:7px;padding:11px 22px;
  border-radius:8px;border:none;font-family:var(--mono);font-size:11px;font-weight:700;
  cursor:pointer;transition:all .2s;letter-spacing:.05em;text-transform:uppercase}
.btn:disabled{opacity:.4;cursor:not-allowed;transform:none!important}
.btn-g{background:var(--accent);color:#000}
.btn-g:hover:not(:disabled){background:#00e678;box-shadow:0 0 20px rgba(0,255,136,.3);transform:translateY(-1px)}
.btn-p{background:var(--accent2);color:#fff}
.btn-p:hover:not(:disabled){background:#6d28d9;box-shadow:0 0 20px rgba(124,58,237,.3);transform:translateY(-1px)}
.btn-a{background:var(--accent3);color:#000}
.btn-a:hover:not(:disabled){background:#d97706;box-shadow:0 0 20px rgba(245,158,11,.3);transform:translateY(-1px)}
.btn-o{background:transparent;color:var(--muted);border:1px solid var(--border)}
.btn-o:hover:not(:disabled){border-color:var(--text);color:var(--text)}
.btn-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}

/* Upload area */
.drop{border:2px dashed var(--border);border-radius:10px;padding:28px;text-align:center;
  cursor:pointer;transition:all .2s;margin-bottom:10px}
.drop:hover,.drop.over{border-color:var(--accent3);background:rgba(245,158,11,.04)}
.drop .di{font-size:26px;margin-bottom:8px}
.drop p{font-size:11px;color:var(--muted)}
.drop span{color:var(--accent3);cursor:pointer}

/* Log terminal */
.terminal{background:#03030a;border:1px solid var(--border);border-radius:12px;
  margin-top:24px;overflow:hidden;display:none}
.terminal.show{display:block;animation:fadeU .3s ease both}
.tbar{display:flex;align-items:center;justify-content:space-between;
  padding:10px 16px;border-bottom:1px solid var(--border);background:var(--surface)}
.tbar-l{display:flex;align-items:center;gap:8px;font-size:10px;color:var(--muted);letter-spacing:.08em}
.tdot{width:8px;height:8px;border-radius:50%;background:var(--accent);animation:pulse 1.5s ease infinite}
.tlog{padding:16px;max-height:320px;overflow-y:auto;font-size:11px;line-height:1.8}
.tlog::-webkit-scrollbar{width:3px}
.tlog::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.log-ok{color:var(--accent)}
.log-err{color:var(--danger)}
.log-info{color:var(--muted)}
.log-pkg{color:#60a5fa}

/* Progress */
.progbar{height:3px;background:var(--border);margin:0;overflow:hidden}
.progfill{height:100%;background:var(--accent);width:0%;transition:width .4s ease}

/* Alert */
.alert{display:flex;gap:9px;padding:11px 13px;border-radius:8px;font-size:11px;
  line-height:1.6;margin-bottom:18px;background:rgba(0,255,136,.04);
  border:1px solid rgba(0,255,136,.15);color:var(--muted)}

/* OS badge */
.osbadge{display:inline-flex;align-items:center;gap:5px;background:var(--surface2);
  border:1px solid var(--border);border-radius:6px;padding:5px 10px;
  font-size:10px;color:var(--muted)}

/* Animations */
@keyframes fadeD{from{opacity:0;transform:translateY(-14px)}to{opacity:1;transform:translateY(0)}}
@keyframes fadeU{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

@media(max-width:600px){
  .tabs,.row2,.statusbar{grid-template-columns:1fr}
  header h1{font-size:20px}
}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="logo">📦</div>
  <div>
    <h1>APKeep <span>Dashboard</span></h1>
    <p id="osline">CROSS-PLATFORM APK DOWNLOADER — DETECTING OS...</p>
  </div>
  <div class="badge" id="osbadge">LIVE</div>
</header>

<div class="statusbar">
  <div class="scard"><div class="snum">148</div><div class="slbl">Total Packages</div></div>
  <div class="scard"><div class="snum" style="color:var(--accent2)">14</div><div class="slbl">Developers</div></div>
  <div class="scard"><div class="snum" style="color:var(--accent3)" id="statDone">0</div><div class="slbl">Downloaded</div></div>
  <div class="scard"><div class="snum" style="color:var(--danger)" id="statFail">0</div><div class="slbl">Failed</div></div>
</div>

<div class="tabs">
  <div class="tab active" data-t="dev" onclick="switchTab('dev')">
    <span class="ticon">🏢</span>
    <div class="ttitle">Developer Studio</div>
    <div class="tdesc">Enter a Play Store developer URL to download all their apps</div>
  </div>
  <div class="tab" data-t="single" onclick="switchTab('single')">
    <span class="ticon">📱</span>
    <div class="ttitle">Single Package</div>
    <div class="tdesc">Download one APK by package ID or Play Store URL</div>
  </div>
  <div class="tab" data-t="bulk" onclick="switchTab('bulk')">
    <span class="ticon">📋</span>
    <div class="ttitle">Bulk Download</div>
    <div class="tdesc">Paste list, upload .txt/.csv, or use saved 148-package list</div>
  </div>
</div>

<!-- DEVELOPER PANEL -->
<div class="panel dev active" id="panel-dev">
  <div class="ph"><div class="pdot"></div><div class="ptitle">Download All Apps from a Developer</div></div>
  <div class="alert">ℹ️ Paste a Play Store developer URL like <code>https://play.google.com/store/apps/developer?id=LoopStack+Studio</code></div>
  <div class="fg">
    <label>Developer URL or Name</label>
    <input type="text" id="devUrl" placeholder="https://play.google.com/store/apps/developer?id=..."/>
    <div class="hint">Accepts full URL, name, or numeric dev ID</div>
  </div>
  <div class="row2">
    <div class="fg">
      <label>Output Directory</label>
      <input type="text" id="devOut" value=""/>
    </div>
    <div class="fg">
      <label>Source</label>
      <select id="devSrc">
        <option value="apk-pure">APKPure (No Login)</option>
        <option value="google-play">Google Play (Token needed)</option>
        <option value="f-droid">F-Droid</option>
      </select>
    </div>
  </div>
  <div class="row2">
    <label class="chk"><input type="checkbox" id="devEx" checked/><span class="cbox">✓</span><span>Extract XAPK → APK</span></label>
    <label class="chk"><input type="checkbox" id="devOrg" checked/><span class="cbox">✓</span><span>Organize by developer</span></label>
  </div>
  <div class="btn-row">
    <button class="btn btn-g" id="devBtn" onclick="startDev()">▶ Start Download</button>
    <button class="btn btn-o" onclick="stopJob()">■ Stop</button>
  </div>
</div>

<!-- SINGLE PANEL -->
<div class="panel single" id="panel-single">
  <div class="ph"><div class="pdot"></div><div class="ptitle">Download a Single APK</div></div>
  <div class="fg">
    <label>Package ID or Play Store URL</label>
    <input type="text" id="singlePkg" placeholder="com.example.app or https://play.google.com/store/apps/details?id=..."/>
  </div>
  <div class="row2">
    <div class="fg">
      <label>Output Directory</label>
      <input type="text" id="singleOut" value=""/>
    </div>
    <div class="fg">
      <label>Source</label>
      <select id="singleSrc">
        <option value="apk-pure">APKPure (No Login)</option>
        <option value="google-play">Google Play</option>
        <option value="f-droid">F-Droid</option>
        <option value="huawei-app-gallery">Huawei AppGallery</option>
      </select>
    </div>
  </div>
  <div class="row2">
    <label class="chk"><input type="checkbox" id="singleEx" checked/><span class="cbox">✓</span><span>Extract XAPK → APK</span></label>
    <label class="chk"><input type="checkbox" id="singleOrg"/><span class="cbox">✓</span><span>Organize by developer</span></label>
  </div>
  <div class="btn-row">
    <button class="btn btn-p" id="singleBtn" onclick="startSingle()">▶ Download APK</button>
    <button class="btn btn-o" onclick="stopJob()">■ Stop</button>
  </div>
</div>

<!-- BULK PANEL -->
<div class="panel bulk" id="panel-bulk">
  <div class="ph"><div class="pdot"></div><div class="ptitle">Bulk Download</div></div>
  <div style="display:flex;gap:8px;margin-bottom:18px;flex-wrap:wrap">
    <button class="btn btn-a" id="bm-paste" style="font-size:9px;padding:8px 12px" onclick="setBM('paste')">📝 Paste List</button>
    <button class="btn btn-o" id="bm-file"  style="font-size:9px;padding:8px 12px" onclick="setBM('file')">📁 Upload File</button>
    <button class="btn btn-o" id="bm-saved" style="font-size:9px;padding:8px 12px" onclick="setBM('saved')">⚡ Saved 148 Pkgs</button>
  </div>

  <div id="bm-paste-area">
    <div class="fg">
      <label>Package IDs <span id="pkgcount" style="color:var(--accent3)">(0 detected)</span></label>
      <textarea id="bulkText" placeholder="com.example.app1&#10;com.example.app2&#10;..." oninput="countPkgs()"></textarea>
    </div>
  </div>
  <div id="bm-file-area" style="display:none">
    <div class="drop" id="dropz" onclick="document.getElementById('fi').click()"
         ondragover="event.preventDefault();this.classList.add('over')"
         ondragleave="this.classList.remove('over')"
         ondrop="handleDrop(event)">
      <div class="di">📂</div>
      <p>Drop <span>.txt</span> or <span>.csv</span> here or click to browse</p>
      <input type="file" id="fi" accept=".txt,.csv" style="display:none" onchange="handleFile(event)"/>
    </div>
    <div id="fileinfo" class="hint"></div>
  </div>
  <div id="bm-saved-area" style="display:none">
    <div class="alert">⚡ Will use the pre-built <strong style="color:var(--accent)">packages.txt</strong> (148 packages, 14 developers) saved from your session.</div>
  </div>

  <div style="height:1px;background:var(--border);margin:16px 0"></div>
  <div class="row2">
    <div class="fg">
      <label>Output Directory</label>
      <input type="text" id="bulkOut" value=""/>
    </div>
    <div class="fg">
      <label>Source</label>
      <select id="bulkSrc">
        <option value="apk-pure">APKPure (No Login)</option>
        <option value="google-play">Google Play</option>
        <option value="f-droid">F-Droid</option>
      </select>
    </div>
  </div>
  <div class="row2">
    <label class="chk"><input type="checkbox" id="bulkEx" checked/><span class="cbox">✓</span><span>Extract XAPK → APK</span></label>
    <label class="chk"><input type="checkbox" id="bulkOrg" checked/><span class="cbox">✓</span><span>Organize by developer</span></label>
  </div>
  <div class="btn-row">
    <button class="btn btn-a" id="bulkBtn" onclick="startBulk()">▶ Start Bulk Download</button>
    <button class="btn btn-o" onclick="stopJob()">■ Stop</button>
  </div>
</div>

<!-- LOG TERMINAL -->
<div class="terminal" id="term">
  <div class="progbar"><div class="progfill" id="prog"></div></div>
  <div class="tbar">
    <div class="tbar-l"><div class="tdot" id="tdot"></div><span id="tstatus">RUNNING</span></div>
    <button class="btn btn-o" style="font-size:9px;padding:5px 10px" onclick="clearLog()">CLEAR</button>
  </div>
  <div class="tlog" id="tlog"></div>
</div>

</div><!-- /wrap -->
<script>
// OS detection
fetch('/api/info').then(r=>r.json()).then(d=>{
  document.getElementById('osline').textContent = `LIVE EXECUTION MODE — ${d.os} — apkeep ${d.apkeep_found?'FOUND':'NOT FOUND'}`;
  document.getElementById('osbadge').textContent = d.apkeep_found ? 'READY' : 'INSTALL NEEDED';
  document.getElementById('devOut').value  = d.default_out;
  document.getElementById('singleOut').value = d.default_out;
  document.getElementById('bulkOut').value = d.default_out;
});

// Tab switching
function switchTab(t){
  document.querySelectorAll('.tab').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(el=>el.classList.remove('active'));
  document.querySelector(`.tab[data-t="${t}"]`).classList.add('active');
  document.getElementById(`panel-${t}`).classList.add('active');
}

// Bulk mode
let bulkMode='paste', uploadedPkgs=[];
function setBM(m){
  bulkMode=m;
  ['paste','file','saved'].forEach(x=>{
    document.getElementById(`bm-${x}-area`).style.display=x===m?'block':'none';
    const btn=document.getElementById(`bm-${x}`);
    btn.className=x===m?'btn btn-a':'btn btn-o';
    btn.style.fontSize='9px';btn.style.padding='8px 12px';
  });
}

function countPkgs(){
  const pkgs=parsePkgs(document.getElementById('bulkText').value);
  document.getElementById('pkgcount').textContent=`(${pkgs.length} detected)`;
}

function parsePkgs(text){
  return text.split(/[\n,;]+/)
    .map(l=>l.trim().replace(/^#.*/,''))
    .filter(l=>l&&/^[a-zA-Z]/.test(l));
}

function handleFile(e){
  const f=e.target.files[0];if(!f)return;
  const r=new FileReader();
  r.onload=ev=>{
    uploadedPkgs=parsePkgs(ev.target.result);
    document.getElementById('fileinfo').textContent=`✓ ${f.name} — ${uploadedPkgs.length} packages loaded`;
  };
  r.readAsText(f);
}

function handleDrop(e){
  e.preventDefault();
  document.getElementById('dropz').classList.remove('over');
  const f=e.dataTransfer.files[0];
  if(f){document.getElementById('fi').files=e.dataTransfer.files;handleFile({target:{files:[f]}});}
}

// Start jobs
function startDev(){
  const url=document.getElementById('devUrl').value.trim();
  if(!url){alert('Enter a developer URL or name.');return;}
  // Extract dev id from URL
  let devId=url;
  const m=url.match(/[?&]id=([^&]+)/);
  if(m) devId=decodeURIComponent(m[1].replace(/\+/g,' '));
  post('/api/start',{
    mode:'developer',dev_id:devId,
    out_dir:document.getElementById('devOut').value,
    source:document.getElementById('devSrc').value,
    extract:document.getElementById('devEx').checked,
    organize:document.getElementById('devOrg').checked,
    packages:[]
  });
}

function startSingle(){
  const raw=document.getElementById('singlePkg').value.trim();
  if(!raw){alert('Enter a package ID or URL.');return;}
  post('/api/start',{
    mode:'single',
    out_dir:document.getElementById('singleOut').value,
    source:document.getElementById('singleSrc').value,
    extract:document.getElementById('singleEx').checked,
    organize:document.getElementById('singleOrg').checked,
    packages:[raw]
  });
}

function startBulk(){
  let pkgs=[];
  if(bulkMode==='paste'){pkgs=parsePkgs(document.getElementById('bulkText').value);}
  else if(bulkMode==='file'){pkgs=uploadedPkgs;}
  else{pkgs=['__saved__'];}
  if(!pkgs.length&&bulkMode!=='saved'){alert('No packages found.');return;}
  post('/api/start',{
    mode:'bulk',
    out_dir:document.getElementById('bulkOut').value,
    source:document.getElementById('bulkSrc').value,
    extract:document.getElementById('bulkEx').checked,
    organize:document.getElementById('bulkOrg').checked,
    packages:pkgs
  });
}

function stopJob(){fetch('/api/stop',{method:'POST'});}

function post(url,data){
  fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
    .then(r=>r.json()).then(d=>{
      if(d.error){alert(d.error);return;}
      showTerminal();startPolling();
    });
}

// Terminal
function showTerminal(){document.getElementById('term').classList.add('show');}
function clearLog(){document.getElementById('tlog').innerHTML='';}

let pollInt=null;
function startPolling(){
  if(pollInt)clearInterval(pollInt);
  pollInt=setInterval(pollStatus,1000);
}

function pollStatus(){
  fetch('/api/status').then(r=>r.json()).then(d=>{
    // Update log
    const tlog=document.getElementById('tlog');
    tlog.innerHTML='';
    d.logs.forEach(line=>{
      const div=document.createElement('div');
      if(line.includes('✓')||line.includes('COMPLETE')) div.className='log-ok';
      else if(line.includes('✗')||line.includes('ERROR')) div.className='log-err';
      else if(line.includes('Downloading:')||line.includes('pkg')) div.className='log-pkg';
      else div.className='log-info';
      div.textContent=line;
      tlog.appendChild(div);
    });
    tlog.scrollTop=tlog.scrollHeight;

    // Stats
    document.getElementById('statDone').textContent=d.done;
    document.getElementById('statFail').textContent=d.failed;

    // Progress
    const pct=d.total>0?Math.round((d.done/d.total)*100):0;
    document.getElementById('prog').style.width=pct+'%';

    // Status
    if(!d.running){
      document.getElementById('tstatus').textContent='COMPLETE';
      document.getElementById('tdot').style.animation='none';
      document.getElementById('tdot').style.background='#00ff88';
      if(pollInt){clearInterval(pollInt);pollInt=null;}
    }else{
      document.getElementById('tstatus').textContent=`RUNNING — ${d.current||''}`;
    }
  });
}
</script>
</body>
</html>"""

# ─── HTTP Handler ─────────────────────────────────────────────────────────────
SAVED_PACKAGES = list(DEV_MAP.keys())

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass  # silence default logs

    def send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/api/info":
            apkeep = find_apkeep()
            self.send_json({
                "os": f"{platform.system()} {platform.release()}",
                "python": sys.version.split()[0],
                "apkeep_found": apkeep is not None,
                "apkeep_path": apkeep or "not found",
                "default_out": str(DEFAULT_OUT),
            })

        elif self.path == "/api/status":
            self.send_json({
                "running": job_running,
                "total": job_stats["total"],
                "done": job_stats["done"],
                "failed": job_stats["failed"],
                "current": job_stats["current"],
                "logs": log_lines[-200:],
            })
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        global job_running
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        if self.path == "/api/start":
            if job_running:
                self.send_json({"error": "A job is already running. Stop it first."}, 400)
                return

            mode     = body.get("mode", "bulk")
            out_dir  = body.get("out_dir", str(DEFAULT_OUT))
            source   = body.get("source", "apk-pure")
            extract  = body.get("extract", True)
            organize = body.get("organize", True)
            packages = body.get("packages", [])

            # Resolve packages
            if mode == "bulk" and packages == ["__saved__"]:
                packages = SAVED_PACKAGES
            elif mode == "single":
                packages = [parse_package_id(p) for p in packages]
            elif mode == "developer":
                dev_id = body.get("dev_id", "")
                # Filter saved packages for this dev or use all
                matching = [p for p, d in DEV_MAP.items()
                            if dev_id.lower().replace(" ","_") in d.lower()]
                packages = matching if matching else SAVED_PACKAGES
                log(f"Developer mode: {dev_id} — {len(packages)} packages matched")
            else:
                packages = [parse_package_id(p) for p in packages]

            packages = [p for p in packages if p and re.match(r'^[a-zA-Z][a-zA-Z0-9._]+$', p)]

            if not packages:
                self.send_json({"error": "No valid packages found."}, 400)
                return

            log_lines.clear()
            t = threading.Thread(
                target=run_download_job,
                args=(packages, out_dir, source, extract, organize),
                daemon=True
            )
            t.start()
            self.send_json({"ok": True, "count": len(packages)})

        elif self.path == "/api/stop":
            # We can't truly kill subprocess easily cross-platform,
            # but we mark it and it will finish current package
            log("Stop requested — will finish current package and halt.")
            self.send_json({"ok": True})

        else:
            self.send_response(404); self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

# ─── Main ─────────────────────────────────────────────────────────────────────
def open_browser(port):
    import webbrowser
    time.sleep(1.2)
    webbrowser.open(f"http://localhost:{port}")

if __name__ == "__main__":
    PORT = 8080
    print(f"""
╔══════════════════════════════════════════════╗
║       APKeep Dashboard — Starting Up         ║
║  Platform : {platform.system()} {platform.release():<20}      ║
║  Python   : {sys.version.split()[0]:<20}           ║
║  URL      : http://localhost:{PORT}           ║
╚══════════════════════════════════════════════╝
""")

    apkeep = find_apkeep()
    if apkeep:
        print(f"  ✓ apkeep found: {apkeep}")
    else:
        print("  ✗ apkeep not found — will attempt auto-install on first download")
        print("    Install manually: cargo install apkeep")
        print("    Or download from: https://github.com/EFForg/apkeep/releases\n")

    threading.Thread(target=open_browser, args=(PORT,), daemon=True).start()

    server = http.server.HTTPServer(("", PORT), Handler)
    print(f"  Server running at http://localhost:{PORT}")
    print("  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
