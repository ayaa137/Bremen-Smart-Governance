# Run from the repository root. Stages rendering; never overwrites an output.
@'
from pathlib import Path
import tempfile, shutil, subprocess, os, hashlib, json
root = Path.cwd()
expected = json.loads((root/'reports/section2_enhanced/pdf_render_validation.json').read_text())['sha256']
env = os.environ.copy()
env['SOURCE_DATE_EPOCH'] = '0'
quarto = Path(os.environ['ProgramFiles'])/'Quarto'
blobs = []
with tempfile.TemporaryDirectory(prefix='bremen-enhanced-pdf-') as temporary:
    for run in range(2):
        stage = Path(temporary)/str(run)
        report = stage/'reports/section2_enhanced'
        figures = stage/'figures/section2_enhanced'
        report.mkdir(parents=True)
        figures.mkdir(parents=True)
        shutil.copy2(root/'reports/section2_enhanced/section2_enhanced.qmd', report)
        for figure in (root/'figures/section2_enhanced').glob('*.png'):
            shutil.copy2(figure, figures)
        with (stage/'render.log').open('w') as log:
            # Default Typst root rejects ../../figures; retain intermediate source.
            subprocess.run([str(quarto/'bin/quarto.exe'), 'render', 'section2_enhanced.qmd', '--to', 'typst', '--no-clean', '--output', 'section2_enhanced.pdf'], cwd=report, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, timeout=55)
            result = subprocess.run([str(quarto/'bin/tools/x86_64/typst.exe'), 'compile', '--root', str(stage), '--package-path', str(quarto/'share/formats/typst/packages'), '--creation-timestamp', '0', 'section2_enhanced.typ', 'section2_enhanced.pdf'], cwd=report, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, timeout=55)
        if result.returncode:
            raise RuntimeError((stage/'render.log').read_text())
        blobs.append((report/'section2_enhanced.pdf').read_bytes())
assert blobs[0] == blobs[1], 'Non-identical PDF builds'
assert hashlib.sha256(blobs[0]).hexdigest() == expected, 'PDF differs from validated artifact'
destination = root/'reports/section2_enhanced/section2_enhanced.pdf'
if destination.exists():
    assert destination.read_bytes() == blobs[0], 'Existing PDF differs; preserved without overwrite'
else:
    with destination.open('xb') as output:
        output.write(blobs[0])
print('PASS: two identical PDF builds; existing outputs preserved')
'@ | & .venv-section2\Scripts\python.exe -B -
if ($LASTEXITCODE -ne 0) { throw 'PDF validation failed' }
