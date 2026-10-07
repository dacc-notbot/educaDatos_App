import subprocess
import tarfile

import pytest

from scripts.sincronizar_respaldo import sincronizar


def preparar_repo(path, archivos):
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    for nombre, contenido in archivos.items():
        (path / nombre).write_text(contenido)
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=Pruebas", "-c", "user.email=pruebas@example.invalid", "commit", "-qm", "Inicial"], check=True)


def test_respaldo_conserva_historial_verifica_archivo_y_es_repetible(tmp_path):
    source, dest, archives = tmp_path / "principal", tmp_path / "respaldo", tmp_path / "archivos"
    preparar_repo(source, {"main.py": "actualizado\n", ".gitignore": ".env\n.backup-state.json\n"})
    preparar_repo(dest, {"main.py": "antiguo\n", "legacy.py": "histórico\n"})
    head = subprocess.check_output(["git", "-C", str(dest), "rev-parse", "HEAD"])
    sincronizar(source, dest, archives)
    assert (dest / "main.py").read_text() == "antiguo\n"
    sincronizar(source, dest, archives, apply=True)
    assert (dest / "main.py").read_text() == "actualizado\n"
    assert not (dest / "legacy.py").exists()
    assert subprocess.check_output(["git", "-C", str(dest), "rev-parse", "HEAD"]) == head
    archive = next(archives.glob("*.tar.gz"))
    with tarfile.open(archive) as saved:
        assert saved.extractfile("respaldo/legacy.py").read() == "histórico\n".encode()
        assert saved.getmember("respaldo/.git/HEAD").isfile()
    sincronizar(source, dest, archives, apply=True)
    assert len(list(archives.glob("*.tar.gz"))) == 1
    (source / "main.py").write_text("nueva versión\n")
    sincronizar(source, dest, archives, apply=True)
    assert (dest / "main.py").read_text() == "nueva versión\n"


def test_cambios_en_respaldo_no_se_sobrescriben(tmp_path):
    source, dest, archives = tmp_path / "principal", tmp_path / "respaldo", tmp_path / "archivos"
    preparar_repo(source, {"main.py": "principal\n", ".gitignore": ".backup-state.json\n"})
    preparar_repo(dest, {"main.py": "original\n"})
    sincronizar(source, dest, archives, apply=True)
    (dest / "main.py").write_text("cambio manual\n")
    with pytest.raises(ValueError, match="no se sobrescribirá"):
        sincronizar(source, dest, archives, apply=True)
    assert (dest / "main.py").read_text() == "cambio manual\n"
