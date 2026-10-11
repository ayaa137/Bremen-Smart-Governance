"""Read-only checks, including an isolated essential-file checkout simulation."""
from pathlib import Path
import sys, subprocess, tempfile, shutil, json, hashlib, re

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src/section2_enhanced'))
import build_enhancement as enhanced

def main():
    manifest=json.loads((ROOT/'reports/section2_enhanced/reproducibility_manifest.json').read_text())
    mismatches=[]
    for group in ['outputs','protected_input_hashes','enhancement_source_hashes']:
        for name,digest in manifest[group].items():
            if enhanced.sha(ROOT/name)!=digest:
                mismatches.append(name)
    assert set(mismatches)=={'src/analyze_section2_v2.py','src/section2_enhanced/build_enhancement.py'}, mismatches
    draft=(Path(__file__).parent/'section2_data_and_indicator_analysis.md').read_text(encoding='utf-8')
    body,captions=draft.split('Figure 1. Economic maps, 2024.')
    headings=[line for line in body.splitlines() if line.startswith('## ')]
    main_text='\n'.join(line for line in body.splitlines() if not line.startswith('## '))
    captions='Figure 1. Economic maps, 2024.'+captions
    counts={'main_text':len(main_text.split()),'captions':len(captions.split()),
            'headings':sum(len(line.removeprefix('## ').split()) for line in headings)}
    counts['main_plus_captions']=counts['main_text']+counts['captions']
    counts['including_headings']=counts['main_plus_captions']+counts['headings']
    assert 290<=counts['including_headings']<=295
    for label in ['Figure 1','Figure 2','Figure 3']:assert label in main_text
    import pandas as pd
    distributions=pd.read_csv(ROOT/'reports/section2_enhanced/distribution_robustness.csv')
    unemployment=distributions[(distributions.feature=='unemployment') & (distributions['sample']=='available')].iloc[0]
    assert abs(unemployment.minimum-2.5896)<1e-10 and abs(unemployment.maximum-27.5409)<1e-10
    assert unemployment.minimum_names=='Seehausen' and unemployment.maximum_names=='Ohlenhof'
    correlations=pd.read_csv(ROOT/'reports/section2_enhanced/correlation_robustness.csv')
    pair=correlations[(correlations['first']=='unemployment') & (correlations['second']=='benefit_receipt') & (correlations['sample']=='complete')].iloc[0]
    assert pair.n==79 and round(pair.spearman_rho,6)==0.973856 and round(pair.kendall_tau_b,6)==0.874716
    omissions=pd.read_csv(ROOT/'reports/section2_enhanced/correlation_leave_one_out.csv')
    assert any(round(value,6)==0.972837 for value in omissions.select_dtypes('number').min())
    assert any(round(value,6)==0.977769 for value in omissions.select_dtypes('number').max())
    qmd=ROOT/'reports/section2_enhanced/section2_enhanced.qmd'
    images={str((qmd.parent/name).resolve().relative_to(ROOT)).replace('\\','/')
            for name in re.findall(r'\]\(([^)]+\.png)\)',qmd.read_text())}
    images.add('figures/section2_enhanced/fig03_economic_indicator_relationships_2024.png')
    assert all((ROOT/name).is_file() for name in images)
    untracked={p for p in subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0') if p}
    optional={p for p in untracked if p.startswith('figures/section2_enhanced/') and p not in images}
    optional.update({'reports/section2_enhanced/section2_enhanced.html','reports/section2_enhanced/section2_enhanced.pdf','reports/section2_enhanced/pdf_feasibility_check.json'})
    essential=untracked-optional
    tracked={p for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if p}
    with tempfile.TemporaryDirectory(prefix='bremen-essential-checkout-') as td:
        stage=Path(td)
        for name in tracked|essential:
            if not (ROOT/name).is_file():continue
            target=stage/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,target)
        shutil.copytree(ROOT/'.git',stage/'.git')
        code="""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src/section2_enhanced'))
import build_enhancement as e
args=e.verify_existing()
master,complete,tables,summary=e.analyze(args[0],args[3],args[2],args[4])
for name,table in tables.items():
    existing=Path('reports/section2_enhanced')/name
    if existing.exists():
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/name;e.csv(table,p)
            assert e.sha(p)==e.sha(existing),name
# Simulate Git metadata only: no commit or branch operation is performed.
original=e.v2.git
for branch,head in [('feature/section2-test','a'*40),('', 'b'*40)]:
    def simulated(*args):
        if args==('branch','--show-current'):return branch
        if args==('rev-parse','HEAD'):return head
        if args==('rev-parse','origin/main'):raise AssertionError('Remote ref must not be required')
        return original(*args)
    e.v2.git=simulated
    e.verify_existing()
e.v2.git=original
print(json.dumps({'status':'PASS','rows':len(master),'complete':len(complete),'independent_tables':len(tables),'simulated_git_states':['feature descendant','detached HEAD; no origin/main query']}))
"""
        result=subprocess.run([sys.executable,'-B','-c',code],cwd=stage,capture_output=True,text=True,timeout=60)
        if result.returncode:raise RuntimeError(result.stderr)
        clean=json.loads(result.stdout.strip())
    result={'word_count_method':'Whitespace-delimited words; Markdown heading markers excluded.',
            'word_counts':counts,'historical_artifacts_preserved':True,
            'approved_modified_scripts':sorted(set(mismatches)),
            'essential_untracked_files_tested':len(essential),'clean_essential_checkout':clean,
            'qmd_png_references':len(images)-1,'git_mutations_performed':False,
            'scope':'No analysis entry point or renderer run in clean simulation; source/hash/schema/geography validators and independent statistical tables checked.'}
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
