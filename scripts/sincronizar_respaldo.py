#!/usr/bin/env python3
"""Actualiza una copia Git local conservando su remoto e historial originales."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def huella(path):
    if path.is_symlink():
        raise ValueError(f"No se sincronizan enlaces simbólicos: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def archivos(root):
    nombres = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
    return {
        nombre for nombre in nombres if nombre and (root / nombre).is_file()
        and not (Path(nombre).name.startswith(".env") and Path(nombre).name != ".env.example")
        and Path(nombre).name != ".backup-state.json"
    }


def sincronizar(source, destination, archive_dir, apply=False):
    source, destination, archive_dir = map(lambda p: Path(p).resolve(), (source, destination, archive_dir))
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("El principal y el respaldo deben ser directorios separados.")
    for root in (source, destination):
        if Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve() != root:
            raise ValueError(f"No es una raíz Git: {root}")
        if not (root / ".git").is_dir():
            raise ValueError("Solo se admiten checkouts con metadatos .git internos.")
    if source == archive_dir or destination == archive_dir or source in archive_dir.parents or destination in archive_dir.parents:
        raise ValueError("Los archivos de recuperación deben estar fuera de ambos repositorios.")
    state_path = destination / ".backup-state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else None
    original = archivos(destination)
    if state is None:
        if git(destination, "status", "--porcelain").strip():
            raise ValueError("El respaldo tiene cambios previos; presérvalos antes de la primera sincronización.")
        managed = original
    else:
        managed = set(state["files"])
        if any(huella(destination / name) != digest for name, digest in state["files"].items()):
            raise ValueError("El respaldo cambió desde la última copia; no se sobrescribirá.")
        if original - managed:
            raise ValueError("Hay archivos nuevos en el respaldo; revísalos antes de sincronizar.")
    names = archivos(source)
    fingerprints = {name: huella(source / name) for name in sorted(names)}
    changed = [name for name, digest in fingerprints.items() if huella(destination / name) != digest]
    removed = sorted(managed - names)
    print(f"Principal: {source}\nRespaldo: {destination}")
    print(f"Archivos nuevos/modificados: {len(changed)}; archivos obsoletos: {len(removed)}")
    if not apply:
        print("Simulación. Usa --apply para guardar una copia recuperable y sincronizar.")
        return
    if not changed and not removed and state is not None:
        print("El respaldo ya coincide; no se hizo ningún cambio.")
        return
    archive_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    archive = archive_dir / f"respaldo-antes-{stamp}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(destination, arcname=destination.name)
    archive.chmod(0o600)
    # Validar bytes de todos los archivos, incluidos historial y cambios locales.
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile():
                with tar.extractfile(member) as saved:
                    digest = hashlib.sha256(saved.read()).hexdigest()
                if digest != huella(destination.parent / member.name):
                    raise ValueError("La copia de recuperación no coincide; sincronización cancelada.")
    for name in changed:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
    for name in removed:
        (destination / name).unlink()
    result = {name: huella(destination / name) for name in sorted(names)}
    if result != fingerprints:
        raise ValueError(f"La verificación del respaldo falló. Recuperación: {archive}")
    state_path.write_text(json.dumps({
        "source": str(source), "source_head": git(source, "rev-parse", "HEAD").decode().strip(),
        "archive": str(archive), "files": result,
    }, indent=2) + "\n")
    state_path.chmod(0o600)
    print(f"Copia verificada: {len(result)} archivos. Recuperación anterior: {archive}")
    print("No se enviaron cambios a GitHub ni se modificó el remoto del respaldo.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="/workspace/educaDatos_App")
    parser.add_argument("--destination", default="/workspace/-EduDatos_Colombia_AI")
    parser.add_argument("--archive-dir", default="/workspace/backups/versiones")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    sincronizar(args.source, args.destination, args.archive_dir, args.apply)


if __name__ == "__main__":
    main()
