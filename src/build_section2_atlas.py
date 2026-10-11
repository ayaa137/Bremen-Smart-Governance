"""Additive, reproducible Bremen 2024 atlas; no Section 2 V2 files are overwritten."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
import tempfile
import shutil
import platform
import struct
import zipfile
import html
import re

import numpy as np
import pandas as pd
import scipy
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch, Patch, Rectangle
from matplotlib.colors import ListedColormap, BoundaryNorm, to_rgb
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/section2_v2/atlas'
SOURCES = REPORT / 'sources'
BASE = 'https://geodienste.bremen.de/wfs_verwaltungsgrenzen'
META = 'https://metaver.de/csw/partner/hb?Service=CSW&Request=GetRecordById&Version=2.0.2&id=D9F32B22-C647-42FD-9E95-1344AC57BC46&outputSchema=http://www.isotc211.org/2005/gmd&elementSetName=full'
LAW = 'https://www.transparenz.bremen.de/metainformationen/verordnung-ueber-die-neuordnung-der-stadtbremischen-verwaltungsbezirke-vom-23-februar-1951-70486?asl=bremen203_tpgesetz.c.55340.de&template=20_gp_ifg_meta_detail_d'
PROPOSAL = 'https://www.rathaus.bremen.de/sixcms/media.php/13/20130312_Ortsgesetz_Stadtteil_Oberneuland.pdf'
URLS = {
    'wfs_capabilities.xml': BASE+'?SERVICE=WFS&REQUEST=GetCapabilities',
    'ortsteile_bremen_epsg25832.gml': BASE+'?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=app:Ortsteile_Bremen&SRSNAME=EPSG:25832',
    'boundary_metadata.xml': META,
    'verwaltungsgrenzen_hb.zip':'https://gdi2.geo.bremen.de/inspire/download/Verwaltungsgrenzen/data/Verwaltungsgrenzen_HB.zip',
    'stadtteile_bremen_epsg25832.gml':BASE+'?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=app:Stadtteile_Bremen&SRSNAME=EPSG:25832',
    'administrative_divisions.html':LAW,
    'oberneuland_2013_proposal.pdf':PROPOSAL,
}
NS = {'gml':'http://www.opengis.net/gml/3.2', 'app':'http://www.deegree.org/app',
      'wfs':'http://www.opengis.net/wfs/2.0','gmd':'http://www.isotc211.org/2005/gmd',
      'gco':'http://www.isotc211.org/2005/gco','ows':'http://www.opengis.net/ows/1.1'}
BASELINE='20b79ae817c5d7c7b80e1d93c79d415d47037be7'
FIGURES=ROOT/'figures/section2_v2'
FEATURES=['unemployment','employment','benefit_receipt']
NAMES=['Unemployment quotient','Insured-employment participation','SGB II receipt: under 65']
DENOMINATORS=['Unemployed / (insured employees + unemployed)',
              'Insured employees / population aged 15–<65',
              'SGB II recipients / population under 65']
DATA_SOURCE='Data: Statistisches Landesamt Bremen, supplied Datentabelle.xls; shared ortsteil_analysis_ready.csv.'
BOUNDARY_SOURCE='Boundaries: Landesamt GeoInformation Bremen · ATKIS · dataset revised 11 Dec 2024 · CC BY 4.0.'
GRAY='#d5d5d5'
MAP_FILES=['atlas_unemployment_2024.png','atlas_sgbii_2024.png',
           'atlas_economic_maps_side_by_side_2024.png','atlas_bivariate_economic_2024.png',
           'atlas_data_blind_spots_2024.png','atlas_neighborhood_evidence_cards_2024.png']
REPORT_FILES=['geographic_join_validation.csv','geographic_join_validation.json','geographic_join_validation.md',
              'boundary_source_metadata.json','bivariate_classification_2024.csv','bivariate_class_counts.csv',
              'classification_breaks.json','spatial_missingness_2024.csv','neighborhood_card_data_2024.csv',
              'atlas_methods_results.md','atlas_figure_captions.md','atlas_validation.json','atlas_reproduction_manifest.json']
OWNED={('figures/section2_v2/'+n) for n in MAP_FILES}|{('reports/section2_v2/atlas/'+n) for n in REPORT_FILES}
PINS={
 'wfs_capabilities.xml':'e8b410fb2833210a9b19c2471222dfebe50756e69ae9022059dc72b7527d0d9c',
 'ortsteile_bremen_epsg25832.gml':'e0e52751c91ffe0349040def779373a97fe86c35724a3b6514464a063ee7fc26',
 'boundary_metadata.xml':'e0fafd01db84fe893eacd83cfe84898c8674d853b357af0c0ad27c34e3223b96',
 'verwaltungsgrenzen_hb.zip':'25b6b0ec211ac4e730faae23c1c1fa11adf6c531682ed51aed9bb11616284dfa',
 'stadtteile_bremen_epsg25832.gml':'e8eebb82bff4ab092343252ebeccc6f7c3f2ef3243ede7aa84981882686500f0',
 'administrative_divisions.html':'030c32d38af30ed918251b0d705a64343ae459881f41439f521808b82047ebea',
 'oberneuland_2013_proposal.pdf':'8e6eeb81aaf4181c4044ef3888f7f929042929d1739293804d3cfe73b14f339b'}

def require(condition,message):
    if not condition: raise AssertionError(message)

def git(*args):
    return subprocess.check_output(['git','--no-pager',*args],cwd=ROOT,timeout=30).decode('utf-8').strip()

def rel(p): return Path(p).relative_to(ROOT).as_posix()

def protected_files():
    raw=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT)
    names={x.decode('utf-8') for x in raw.split(b'\0') if x}
    return {n:sha(ROOT/n) for n in sorted(names) if n not in OWNED and (ROOT/n).is_file()}

def read_csv(p):
    return pd.read_csv(ROOT/p,encoding='utf-8-sig',dtype={'geo_code':str},float_precision='round_trip')

def json_text(x): return json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n'

def load_data():
    require(git('branch','--show-current')=='analysis/section-2-v2','Wrong branch')
    require(git('rev-parse','HEAD')==git('rev-parse','origin/main')==BASELINE,'Unapproved baseline')
    require(not git('diff','--name-only','HEAD'),'Shared tracked files have changed')
    old=json.loads((ROOT/'reports/section2_v2/reproduction_manifest.json').read_text(encoding='utf-8'))
    for group in ['protected_input_hashes','outputs']:
        for n,h in old[group].items(): require(sha(ROOT/n)==h,'Section 2 V2 or previous input changed: '+n)
    require(sha(ROOT/'src/analyze_section2_v2.py')==old['script_sha256'],'V2 script changed')
    frame=read_csv('data/processed/ortsteil_analysis_ready.csv').sort_values('geo_code').reset_index(drop=True)
    definitions=read_csv('analysis/indicator_selection.csv')
    pd.testing.assert_frame_equal(definitions,read_csv('analysis/data_dictionary.csv'))
    require(len(frame)==88 and frame.geo_code.is_unique and frame.geo_code.str.fullmatch(r'\d{3}').all(),'Invalid geographic keys')
    require(frame.year.eq(2024).all() and frame.geo_level.eq('Ortsteil').all(),'Wrong year or geographic level')
    eligible=frame[FEATURES].notna().all(axis=1)
    require(eligible.equals(frame.scoring_eligible) and eligible.sum()==79,'Eligibility differs from shared sample')
    require(frame[FEATURES].notna().sum().tolist()==[79,79,84],'Indicator coverage changed')
    for feature in FEATURES:
        require(frame[feature+'_year'].eq(2024).all() and frame[feature+'_unit'].eq('%').all(),'Year/unit mismatch')
        values=frame[feature].dropna()
        require(np.isfinite(values).all() and values.between(0,100).all(),'Invalid percentage')
    definitions=definitions.set_index('feature').loc[FEATURES].reset_index()
    require(definitions.indicator_block.eq(1).all() and definitions.unit.eq('%').all(),'Definition mismatch')
    return frame,definitions

def signed_area(ring):
    r=ring-ring[0]
    return float(np.sum(r[:-1,0]*r[1:,1]-r[1:,0]*r[:-1,1])/2)

def parse_geometry(feature):
    geom=feature.find('app:geom',NS)
    require(geom is not None,'Missing geometry')
    unsupported={'Curve','Arc','ArcString','Circle','CompositeSurface','Surface','PolygonPatch'}
    require(not any(n.tag.split('}')[-1] in unsupported for n in geom.iter()),'Unsupported curved/complex geometry')
    crs={n.attrib['srsName'] for n in geom.iter() if 'srsName' in n.attrib}
    require(crs=={'EPSG:25832'},'Wrong or mixed geometry CRS')
    parts=[]
    for polygon in geom.findall('.//gml:Polygon',NS):
        rings=[]
        for kind in ['exterior','interior']:
            nodes=polygon.findall('gml:'+kind,NS)
            require(kind!='exterior' or len(nodes)==1,'Invalid exterior count')
            for node in nodes:
                pos=node.find('gml:LinearRing/gml:posList',NS)
                require(pos is not None and pos.attrib.get('srsDimension','2')=='2','Unsupported coordinate encoding')
                numbers=np.fromstring(pos.text,sep=' ')
                require(len(numbers)%2==0,'Odd coordinate count')
                ring=numbers.reshape(-1,2)
                require(len(ring)>=4 and np.isfinite(ring).all() and np.array_equal(ring[0],ring[-1]),'Invalid/unclosed ring')
                area=signed_area(ring)
                require(abs(area)>0 and len(np.unique(ring,axis=0))>=3,'Degenerate ring')
                # Matplotlib nonzero winding preserves holes; never simplify original coordinates.
                if (kind=='exterior' and area<0) or (kind=='interior' and area>0): ring=ring[::-1]
                rings.append(ring)
        require(bool(rings),'Empty polygon')
        parts.append(rings)
    require(bool(parts),'No polygon parts')
    return parts

def dbf_rows(z,name):
    b=z.read(name)
    count,header,length=struct.unpack_from('<IHH',b,4)
    fields=[]
    for i in range(32,header-1,32):
        f=b[i:i+32]; fields.append((f[:11].split(b'\0')[0].decode('ascii'),f[16]))
    encoding=z.read(name.replace('.dbf','.cpg')).decode().strip()
    rows=[]
    for i in range(count):
        record=b[header+i*length:header+(i+1)*length]
        require(record[0]==32,'Deleted/invalid DBF record')
        p=1;row={}
        for field,size in fields: row[field]=record[p:p+size].decode(encoding).strip();p+=size
        rows.append(row)
    return rows

def load_geography(frame):
    for name,digest in PINS.items():
        require((SOURCES/name).is_file(),'Missing frozen source '+name+'; atlas requires its archived source snapshots')
        require(sha(SOURCES/name)==digest,'Official source snapshot changed; review required: '+name)
    cap=ET.parse(SOURCES/'wfs_capabilities.xml')
    fees=cap.find('.//ows:Fees',NS).text
    require('4.0' in fees and 'Landesamt GeoInformation Bremen' in fees,'License/attribution unverified')
    meta=ET.parse(SOURCES/'boundary_metadata.xml')
    identification=meta.find('.//gmd:MD_DataIdentification',NS)
    title=identification.find('.//gmd:title/gco:CharacterString',NS).text
    dates=[]
    for node in identification.findall('gmd:citation/gmd:CI_Citation/gmd:date/gmd:CI_Date',NS):
        typ=node.find('gmd:dateType/gmd:CI_DateTypeCode',NS).attrib['codeListValue']
        val=list(node.find('gmd:date',NS))[0].text
        dates.append(dict(type=typ,value=val))
    require(any(d['type']=='revision' and d['value'].startswith('2024-12-11') for d in dates),'Boundary revision unverified')
    text=html.unescape(re.sub('<[^>]+>',' ',(SOURCES/'administrative_divisions.html').read_text(encoding='utf-8')))
    text=' '.join(text.split())
    require(re.search(r'361\s+Oberneuland',text) is not None,'Official 361/Oberneuland code evidence missing')
    polygons={};properties=[];member_ids=[]
    doc=ET.parse(SOURCES/'ortsteile_bremen_epsg25832.gml').getroot()
    features=doc.findall('wfs:member/app:Ortsteile_Bremen',NS)
    for f in features:
        p={c.tag.split('}')[-1]:c.text for c in f if c.tag!='{'+NS['app']+'}geom'}
        require(p['sch_ks']=='04011000' and p['bez_ks']=='Bremen','Unexpected municipality')
        require(re.fullmatch(r'04011\d{3}',p['sch_ot']) is not None,'Unexpected official code')
        code=p['sch_ot'][-3:]
        require(p['sch_ot_ags']=='040110000'+code,'Independent official code fields disagree')
        require(code not in polygons,'Duplicate polygon code')
        member_ids.append(f.attrib['{'+NS['gml']+'}id'])
        polygons[code]=parse_geometry(f)
        properties.append(dict(geo_code=code,boundary_name=p['bez_ot'],official_code=p['sch_ot'],
                               boundary_stadtbezirk=p['bez_sb'],boundary_stadtteil=p.get('bez_st',''),
                               source_level='Ortsteil',source_layer='app:Ortsteile_Bremen',
                               crosswalk='official code suffix; sch_ot_ags independently checked',
                               official_area_km2=float(p['flaeche'])))
    require(len(set(member_ids))==len(member_ids),'Duplicate WFS feature identifier')
    raw_codes=set(polygons)
    require(set(frame.geo_code)-raw_codes=={'361'} and not raw_codes-set(frame.geo_code),'Unexpected unresolved geographic mismatch')
    # Explicit one-to-one exception, not a suffix join between different geographic levels.
    st=ET.parse(SOURCES/'stadtteile_bremen_epsg25832.gml')
    candidates=[f for f in st.findall('wfs:member/app:Stadtteile_Bremen',NS)
                if f.find('app:sch_st',NS).text=='04011360']
    require(len(candidates)==1 and candidates[0].find('app:bez_st',NS).text=='Oberneuland','Oberneuland Stadtteil exception unverified')
    f=candidates[0]
    require(f.find('app:sch_ks',NS).text=='04011000','Wrong Oberneuland municipality')
    polygons['361']=parse_geometry(f)
    properties.append(dict(geo_code='361',boundary_name='Oberneuland',official_code='04011360',
                           boundary_stadtbezirk=f.find('app:bez_sb',NS).text,boundary_stadtteil='Oberneuland',
                           source_level='Stadtteil',source_layer='app:Stadtteile_Bremen',
                           crosswalk='explicit undivided Oberneuland 360 -> statistical 361; official documents',
                           official_area_km2=float(f.find('app:flaeche',NS).text)))
    z=zipfile.ZipFile(SOURCES/'verwaltungsgrenzen_hb.zip')
    rows=dbf_rows(z,'hb_ortsteile_BRE.dbf')
    require(len(rows)==len(features)==87 and {r['SCH_OT'][-3:] for r in rows}==raw_codes,'WFS/shapefile scope differs')
    for p in properties:
        if p['source_level']=='Ortsteil':
            row=next(r for r in rows if r['SCH_OT']==p['official_code'])
            require(row['BEZ_OT']==p['boundary_name'],'WFS/DBF name mismatch')
    geometry_rows=[]
    for code,parts in sorted(polygons.items()):
        area=sum(sum(signed_area(r) for r in rings) for rings in parts)/1e6
        official=next(p['official_area_km2'] for p in properties if p['geo_code']==code)
        # Coordinate precision can create a small difference from published area.
        require(abs(area-official)<max(.001,official*.002),'Geometry/published area mismatch '+code)
        geometry_rows.append(dict(geo_code=code,geometry_parts=len(parts),
                                  geometry_rings=sum(map(len,parts)),coordinate_area_km2=area))
    join=frame[['geo_code','geo_name']].merge(pd.DataFrame(properties),on='geo_code',how='outer',validate='one_to_one',indicator=True)
    require(join['_merge'].eq('both').all() and len(join)==88,'Unresolved join; map production blocked')
    join['name_discrepancy']=join.geo_name.ne(join.boundary_name)
    expected={'437':('Ueberseestadt','Überseestadt'),'421':('Regensburger Straße','Regensburger Str.'),'515':('St. Magnus','St.Magnus')}
    actual={r.geo_code:(r.geo_name,r.boundary_name) for r in join[join.name_discrepancy].itertuples()}
    require(actual==expected,'Unreviewed geographic name discrepancy')
    join=join.merge(pd.DataFrame(geometry_rows),on='geo_code',validate='one_to_one').drop(columns='_merge')
    join['join_status']='matched'
    join['boundary_dataset_revision']='2024-12-11'
    join['crs']='EPSG:25832'
    allpoints=np.concatenate([r for parts in polygons.values() for rings in parts for r in rings])
    extent=[float(v) for v in [allpoints[:,0].min(),allpoints[:,0].max(),allpoints[:,1].min(),allpoints[:,1].max()]]
    report=dict(socioeconomic_records=88,official_ortsteil_features=87,official_feature_ids_unique=True,
                wfs_declared_numberReturned=doc.attrib.get('numberReturned'),wfs_actual_members=len(features),
                raw_unmatched_socioeconomic=[dict(geo_code='361',geo_name='Oberneuland')],raw_unmatched_polygons=[],
                resolved_crosswalks=[dict(geo_code='361',official_code='04011360',source_level='Stadtteil',
                    evidence=[LAW,PROPOSAL],interpretation='Undivided Oberneuland territory; explicit statistical 361 crosswalk, not a general level conversion.')],
                final_matched=88,final_unmatched_socioeconomic=[],final_unmatched_polygons=[],missing_geometries=0,
                name_discrepancies=[dict(geo_code=k,socioeconomic_name=a,boundary_name=b) for k,(a,b) in sorted(actual.items())],
                dataset_revision='2024-12-11',exact_legal_boundary_validity_date_verified=False,
                boundary_compatibility='Same-year dataset revision and explicit code crosswalk; exact statistical boundary reference day remains unverified.',
                scope='88 represented mainland statistical units; no Bremerhaven municipality, no separately represented code 123 overseas-port enclave. Not an all-territory Land Bremen map.',
                geometry_checks='Finite, closed nondegenerate 2-D rings; CRS; original vertices; multipart/hole handling; coordinate area vs published area. No full topology/overlap certification.',
                extent_epsg25832=extent)
    source=dict(dataset_title=title,publishing_authority='Landesamt GeoInformation Bremen',
                source_url='https://metaver.de/trefferanzeige?docuuid=D9F32B22-C647-42FD-9E95-1344AC57BC46',
                direct_download_urls=URLS,geographic_levels=['Ortsteil','Stadtteil (one explicit exception)'],
                boundary_dataset_dates=dates,boundary_dataset_revision='2024-12-11',exact_legal_boundary_validity_date=None,
                crs='EPSG:25832 — ETRS89 / UTM zone 32N',license='Creative Commons Attribution 4.0 International',
                license_url='https://creativecommons.org/licenses/by/4.0/',attribution='Landesamt GeoInformation Bremen',
                formats=['GML 3.2 WFS response','Shapefiles ZIP','ISO XML metadata','official HTML','official PDF'],
                accessed_date='2026-10-10',wfs_snapshot_timestamp=doc.attrib['timeStamp'],
                snapshots={n:dict(url=URLS[n],sha256=PINS[n]) for n in URLS})
    return polygons,join.sort_values('geo_code'),report,source,extent

def classify(values):
    clean=values.dropna()
    breaks=np.quantile(clean.to_numpy(),[1/3,2/3],method='linear')
    require(breaks[0]<breaks[1],'Repeated tertile boundaries; map production requires explicit review')
    # Values exactly on a boundary remain in the lower class; ties are never split.
    out=pd.Series(pd.NA,index=values.index,dtype='Int64')
    out.loc[clean.index]=np.searchsorted(breaks,clean.to_numpy(),side='left')
    return out,[float(v) for v in breaks]

def build_tables(frame):
    pair=frame[frame.unemployment.notna() & frame.benefit_receipt.notna()]
    require(len(pair)==79 and pair.geo_code.tolist()==frame[frame.scoring_eligible].geo_code.tolist(),'Pair sample differs')
    out=frame[['geo_code','geo_name','unemployment','benefit_receipt']].copy()
    labels={0:'lower third',1:'middle third',2:'upper third'}
    breaks={}
    for f in ['unemployment','benefit_receipt']:
        cls,breaks[f]=classify(pair[f])
        out[f+'_class']=pd.Series(pd.NA,index=out.index,dtype='Int64')
        out.loc[pair.index,f+'_class']=cls
        out[f+'_group']=out[f+'_class'].map(labels)
    out['combined_bivariate_category']='missing either indicator'
    for i in pair.index:
        out.loc[i,'combined_bivariate_category']=str(labels[int(out.loc[i,'unemployment_class'])])+' unemployment / '+str(labels[int(out.loc[i,'benefit_receipt_class'])])+' SGB II'
    out['missingness_status']=np.where(frame.unemployment.isna() & frame.benefit_receipt.isna(),'both missing',
                                   np.where(frame.unemployment.isna(),'unemployment missing',
                                   np.where(frame.benefit_receipt.isna(),'SGB II missing','both observed')))
    out['year']=2024
    counts=pd.crosstab(out.unemployment_class,out.benefit_receipt_class).reindex(index=[0,1,2],columns=[0,1,2],fill_value=0)
    require(counts.to_numpy().sum()==79,'Bivariate category count mismatch')
    counts.index.name='unemployment_class'
    counts=counts.reset_index().rename(columns={0:'sgbii_lower_third',1:'sgbii_middle_third',2:'sgbii_upper_third'})
    miss=frame[['geo_code','geo_name','year',*FEATURES,'scoring_eligible']].copy()
    miss['observed_primary_count']=frame[FEATURES].notna().sum(axis=1)
    miss['missing_primary_count']=3-miss.observed_primary_count
    miss['all_three_available']=miss.observed_primary_count.eq(3)
    miss['shared_complete_case']=frame.scoring_eligible
    require(miss.all_three_available.equals(miss.shared_complete_case),'Missingness sample flags disagree')
    miss['geographic_join_status']='matched'
    choices={}
    for feature,ascending,reason in [('unemployment',False,'Highest observed unemployment'),('unemployment',True,'Lowest observed unemployment'),
                                      ('benefit_receipt',False,'Highest observed SGB II receipt')]:
        row=frame.dropna(subset=[feature]).sort_values([feature,'geo_code'],ascending=[ascending,True]).iloc[0]
        choices.setdefault(row.geo_code,[]).append(reason)
    missing=miss[miss.missing_primary_count.eq(miss.missing_primary_count.max())].sort_values('geo_code').iloc[0]
    choices.setdefault(missing.geo_code,[]).append('Missing all economic observations; lowest code among equally incomplete cases')
    med=pair[['unemployment','benefit_receipt']].median()
    disagreement=pair[(pair.unemployment>med.unemployment)&(pair.benefit_receipt<med.benefit_receipt)|
                      (pair.unemployment<med.unemployment)&(pair.benefit_receipt>med.benefit_receipt)]
    require(len(disagreement)==1,'Median disagreement examples changed; review selection')
    choices.setdefault(disagreement.iloc[0].geo_code,[]).append('Only strictly opposite-side median example in the 79-case sample')
    cards=miss[miss.geo_code.isin(choices)].copy()
    order={code:i for i,code in enumerate(choices)}
    cards['selection_reason']=cards.geo_code.map(lambda c:'; '.join(choices[c]))
    cards['display_order']=cards.geo_code.map(order)
    cards=cards.sort_values('display_order').reset_index(drop=True)
    statements={
      '443':'Highest observed unemployment and under-65 SGB II receipt; distinct populations.',
      '261':'Lowest observed unemployment; highest observed insured-employment participation.',
      '122':'All three economic observations are missing; economic conditions cannot be inferred.',
      '382':'Above the unemployment median, below the SGB II median; sample-relative contrast.'}
    require(set(cards.geo_code)==set(statements),'Evidence-card examples changed')
    cards['interpretation']=cards.geo_code.map(statements)
    cards['unit']='%'
    cards['source']='Statistisches Landesamt Bremen; supplied Datentabelle.xls; shared analysis-ready CSV'
    cards['completeness_warning']=np.where(cards.shared_complete_case,'Three observed indicators; denominator/reference-date limitations remain.',
                                           'Missing evidence; excluded from the shared 79-case comparison. Missing is not zero.')
    rho=float(spearmanr(pair.unemployment,pair.benefit_receipt).statistic)
    require(np.isclose(rho,pair[['unemployment','benefit_receipt']].rank().corr().iloc[0,1],atol=1e-14),'Independent rho check failed')
    agreement=int((out.loc[pair.index,'unemployment_class']==out.loc[pair.index,'benefit_receipt_class']).sum())
    classifications=dict(sample_n=79,quantiles=[1/3,2/3],method='numpy linear sample quantiles; values equal to cutpoints assigned to lower class; ties never split',
                          repeated_boundary_rule='Stop map production rather than silently reduce classes or split tied observations',
                          breakpoints_percent=breaks,observed_boundary_ties={f:int(pair[f].isin(breaks[f]).sum()) for f in breaks},
                          value_ties={f:int(pair[f].duplicated(keep=False).sum()) for f in breaks},
                          class_coding='0 lower, 1 middle, 2 upper; missing has no numeric class',same_tertile_n=agreement,
                          differing_tertile_n=79-agreement,spearman_rho=rho,
                          univariate_map_breaks=[0,5,10,15,20,25,30,35],
                          univariate_map_rule='Shared fixed 5-percentage-point bins [a,b), final upper endpoint included. Quantiles only for the bivariate map; no threshold implies official risk.')
    return out,counts,miss,cards,classifications

def polygon_path(parts):
    paths=[]
    for rings in parts:
        for ring in rings:
            codes=np.full(len(ring),MPath.LINETO,dtype=np.uint8);codes[0]=MPath.MOVETO;codes[-1]=MPath.CLOSEPOLY
            paths.append(MPath(ring,codes))
    return MPath.make_compound_path(*paths)

def map_base(ax,polygons,colors,extent):
    require(set(colors)==set(polygons),'Map color keys differ from geometry keys')
    for code,parts in sorted(polygons.items()):
        ax.add_patch(PathPatch(polygon_path(parts),facecolor=colors[code],edgecolor='#535353',lw=.38,joinstyle='round'))
    dx=(extent[1]-extent[0])*.025;dy=(extent[3]-extent[2])*.035
    ax.set_xlim(extent[0]-dx,extent[1]+dx);ax.set_ylim(extent[2]-dy,extent[3]+dy)
    ax.set_aspect('equal');ax.set_axis_off()
    return [list(ax.get_xlim()),list(ax.get_ylim())]

def annotation(ax,polygons,code,label,offset):
    exterior=max((rings[0] for rings in polygons[code]),key=lambda r:abs(signed_area(r)))
    # Polygon-derived annotation anchor; not invented geographic coordinates.
    q=exterior[:-1].mean(axis=0)
    ax.annotate(label,q,xytext=offset,textcoords='offset points',fontsize=8,
                bbox=dict(boxstyle='round,pad=.2',fc='white',ec='#bbbbbb',alpha=.94),
                arrowprops=dict(arrowstyle='-',color='#333333',lw=.6))

def finish(fig,target,notes):
    fig.text(.035,.052,DATA_SOURCE,fontsize=8)
    fig.text(.035,.035,BOUNDARY_SOURCE,fontsize=8)
    fig.text(.035,.018,notes,fontsize=8)
    fig.savefig(target,dpi=300,facecolor='white',metadata={'Software':'Bremen Section 2 Atlas; deterministic Matplotlib export'})
    plt.close(fig)

def make_maps(stage,frame,polygons,extent,biv,miss,classes):
    limits=[]
    breaks=classes['univariate_map_breaks']
    require(frame[['unemployment','benefit_receipt']].max().max()<breaks[-1],'Map breaks fail to cover observed values')
    palette=plt.get_cmap('cividis')(np.linspace(.1,.9,len(breaks)-1))
    cmap=ListedColormap(palette);norm=BoundaryNorm(breaks,cmap.N)
    labels=[f'{a}–<{b}%' for a,b in zip(breaks[:-1],breaks[1:])];labels[-1]='30–35%'
    handles=[Patch(fc=c,ec='#555555',lw=.4,label=l) for c,l in zip(palette,labels)]+[Patch(fc=GRAY,ec='#555555',label='Missing observation')]
    def panel(ax,f,title,legend=True):
        values=frame.set_index('geo_code')[f]
        colors={code:GRAY if pd.isna(v) else cmap(norm(v)) for code,v in values.items()}
        limits.append(map_base(ax,polygons,colors,extent))
        ax.set_title(title,fontsize=14,loc='left',pad=32)
        if legend:ax.legend(handles=handles,title='Observed rate (%)\nShared 5-point intervals',loc='lower left',fontsize=8,title_fontsize=9,frameon=True)
    for f,name,title,denom in [('unemployment',MAP_FILES[0],"Unemployment Across Bremen's Ortsteile, 2024",DENOMINATORS[0]),
                               ('benefit_receipt',MAP_FILES[1],"SGB II Benefit Receipt Across Bremen's Ortsteile, 2024",DENOMINATORS[2])]:
        fig,ax=plt.subplots(figsize=(12,9));fig.subplots_adjust(left=.025,right=.98,bottom=.12,top=.86)
        panel(ax,f,title)
        ax.set_title('')
        fig.suptitle(title,x=.035,ha='left',fontsize=18,y=.97)
        fig.text(.035,.91,denom+' (%)',fontsize=10)
        annotation(ax,polygons,'443','Ohlenhof',(-30,25))
        annotation(ax,polygons,'261','Seehausen',(-44,-25))
        annotation(ax,polygons,'361','Oberneuland*',(5,15))
        finish(fig,stage/name,'88 mapped units; *Oberneuland: documented undivided Stadtteil crosswalk. Boundary legal validity day unverified.')
    fig,axes=plt.subplots(1,2,figsize=(17,8.7));fig.subplots_adjust(left=.025,right=.98,bottom=.15,top=.83,wspace=.07)
    fig.suptitle('Bremen Socioeconomic Inequality Atlas — 2024',x=.035,ha='left',fontsize=19,y=.97)
    for ax,f,title,denom in zip(axes,['unemployment','benefit_receipt'],['Unemployment','SGB II benefit receipt'],[DENOMINATORS[0],DENOMINATORS[2]]):
        panel(ax,f,title)
        ax.text(0,1.02,denom+' (%)',transform=ax.transAxes,fontsize=9)
    finish(fig,stage/MAP_FILES[2],'Ortsteil-level statistical units; n=79 unemployment, n=84 SGB II; missing gray; identical extent and class breaks.')
    # Blue / orange-purple two-dimensional palette; text labels and exported categories supplement color.
    bpalette=np.array([['#e8e8e8','#dfb0d6','#be64ac'],['#ace4e4','#a5add3','#8c62aa'],['#5ac8c8','#5698b9','#3b4994']])
    fig,ax=plt.subplots(figsize=(12,9.5));fig.subplots_adjust(left=.025,right=.98,bottom=.17,top=.85)
    colors={r.geo_code:(GRAY if pd.isna(r.unemployment_class) else bpalette[int(r.unemployment_class),int(r.benefit_receipt_class)]) for r in biv.itertuples()}
    limits.append(map_base(ax,polygons,colors,extent))
    fig.suptitle("Economic Indicator Agreement Across Bremen's Ortsteile, 2024",x=.035,ha='left',fontsize=17,y=.97)
    fig.text(.035,.92,'Relative sample tertiles · 79 paired observations · 9 missing either indicator',fontsize=10)
    legend=fig.add_axes([.065,.21,.18,.20])
    for u in range(3):
        for s in range(3):legend.add_patch(Rectangle((u,s),1,1,fc=bpalette[u,s],ec='white',lw=1))
    legend.set(xlim=(0,3),ylim=(0,3),xticks=[.5,1.5,2.5],yticks=[.5,1.5,2.5])
    legend.set_xticklabels(['Lower','Middle','Upper'],fontsize=8)
    legend.set_yticklabels(['Lower','Middle','Upper'],fontsize=8)
    legend.set_xlabel('Unemployment quotient (%)',fontsize=9)
    legend.set_ylabel('SGB II under-65 receipt (%)',fontsize=9)
    legend.tick_params(length=0)
    fig.text(.065,.155,'Gray = missing either indicator; classes describe observed sample, not official risk.',fontsize=9)
    finish(fig,stage/MAP_FILES[3],'Distinct indicator denominators; full definitions in atlas report. 88 mapped units, including explicit Oberneuland exception.')
    fig,ax=plt.subplots(figsize=(12,9));fig.subplots_adjust(left=.025,right=.98,bottom=.13,top=.86)
    mpalette={0:'#c5dfd5',1:'#f3d3a3',2:'#e5a354',3:'#a85235'}
    colors={r.geo_code:mpalette[int(r.missing_primary_count)] for r in miss.itertuples()}
    limits.append(map_base(ax,polygons,colors,extent))
    fig.suptitle('Where Is Socioeconomic Evidence Missing? Bremen Ortsteile, 2024',x=.035,ha='left',fontsize=17,y=.97)
    fig.text(.035,.915,'Three primary economic indicators · all 88 represented geographic records',fontsize=10)
    nh=miss.missing_primary_count.value_counts()
    h=[Patch(fc=mpalette[k],ec='#555555',label=f'{k} missing / {3-k} observed (n={int(nh.get(k,0))})') for k in range(4)]
    h.append(Patch(fc='white',ec='#333333',hatch='///',label='No socioeconomic record (n=0)'))
    ax.legend(handles=h,title='Missing-indicator count',loc='lower left',fontsize=9,title_fontsize=10)
    annotation(ax,polygons,'122','Industriehäfen: 3 missing',(-90,25))
    annotation(ax,polygons,'411','Blockland: 2 missing',(-65,30))
    finish(fig,stage/MAP_FILES[4],'Missing is not zero; 79 complete, 9 incomplete. No documented explanation for missing observations; no imputation.')
    require(all(np.allclose(l,limits[0],rtol=0,atol=0) for l in limits),'Geographic extents differ between maps')
    return dict(map_extent_axis_limits=limits[0],identical_extents_verified=True,univariate_palette='cividis',
                bivariate_palette=bpalette.tolist(),bivariate_palette_accessibility='Blue/teal–purple palette avoids red/green coding; 3×3 textual legend and CSV provided. No universal color-vision accessibility claim.',
                mapped_keys_each=88,unemployment_colored=79,sgbii_colored=84,bivariate_colored=79,blind_spots_records=88)

def make_cards(stage,cards):
    fig,axes=plt.subplots(2,2,figsize=(15,12));fig.subplots_adjust(left=.10,right=.97,bottom=.27,top=.85,hspace=.90,wspace=.4)
    fig.suptitle('Neighborhood evidence cards · Bremen · Ortsteil · 2024',x=.035,ha='left',fontsize=19,y=.97)
    fig.text(.035,.923,'Four deliberately selected examples; they are not representative of all neighborhoods.',fontsize=11)
    for ax,row in zip(axes.flat,cards.itertuples()):
        vals=[getattr(row,f) for f in FEATURES]
        ax.set_title(f'{row.geo_name} ({row.geo_code})',loc='left',fontsize=14,pad=14,fontweight='bold')
        ax.set_xlim(0,100);ax.set_ylim(-.6,2.65)
        ax.set_yticks([2,1,0],['Unemployment','Employment','SGB II under 65'],fontsize=9)
        ax.set_xlabel('Observed percentage; distinct denominators',fontsize=9)
        ax.set_xticks([0,25,50,75,100]);ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True)
        for y,v,c in zip([2,1,0],vals,['#176d8e','#23816d','#b35639']):
            if pd.isna(v):ax.text(3,y,'MISSING — not zero',va='center',fontsize=10,color='#6a6a6a')
            else:
                ax.barh(y,v,height=.5,color=c)
                ax.text(v+1.5,y,f'{v:.4f}%',va='center',fontsize=9)
        for side in ['top','right']:ax.spines[side].set_visible(False)
        import textwrap
        statement='\n'.join(textwrap.wrap(row.interpretation,72))
        ax.text(0,-.38,statement,transform=ax.transAxes,fontsize=9,va='top')
        ax.text(0,1.02,f'{row.observed_primary_count}/3 observed primary indicators',transform=ax.transAxes,fontsize=9,color='#555555')
    fig.text(.035,.115,'Denominators: unemployment / (insured employees + unemployed); insured employees / population aged 15–<65;',fontsize=9)
    fig.text(.035,.095,'SGB II recipients / population under 65. Values are percentages; all panels use 0–100%.',fontsize=9)
    fig.text(.035,.060,DATA_SOURCE,fontsize=8)
    fig.text(.035,.038,'Selection: unemployment maximum/minimum, SGB II maximum (duplicate removed), first-code wholly missing case, only median-disagreement case.',fontsize=8)
    fig.text(.035,.018,'No official disadvantage classification or allocation recommendation. Missing observations carry no economic interpretation.',fontsize=8)
    fig.savefig(stage/MAP_FILES[5],dpi=300,facecolor='white',metadata={'Software':'Bremen Section 2 Atlas; deterministic Matplotlib export'})
    plt.close(fig)
    return dict(card_n=len(cards),codes=cards.geo_code.tolist(),shared_visual_scale=[0,100],missing_values_not_drawn_as_bars=True)

def markdown_table(frame):
    def text(v):
        if pd.isna(v):return 'missing'
        if isinstance(v,(float,np.floating)):return f'{v:.4f}'
        return str(v).replace('|','\\|').replace('\n',' ')
    lines=['| '+' | '.join(frame.columns)+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    return '\n'.join(lines+['| '+' | '.join(text(v) for v in row)+' |' for row in frame.itertuples(index=False,name=None)])

def documents(frame,definitions,join,geoval,source,biv,counts,miss,cards,classes):
    missing=miss[miss.missing_primary_count.gt(0)][['geo_code','geo_name','observed_primary_count','missing_primary_count']]
    display=cards[['geo_code','geo_name',*FEATURES,'selection_reason','interpretation']]
    same=classes['same_tertile_n'];different=classes['differing_tertile_n']
    cuts=classes['breakpoints_percent']
    groups=biv.merge(join[['geo_code','boundary_stadtbezirk']],on='geo_code',validate='one_to_one')
    high=groups[(groups.unemployment_class==2)&(groups.benefit_receipt_class==2)]
    highdistrict=high.boundary_stadtbezirk.value_counts().sort_index()
    uppernames=', '.join(high.geo_name)
    missingdistrict=miss.merge(join[['geo_code','boundary_stadtbezirk']],on='geo_code',validate='one_to_one')
    incompletedistrict=missingdistrict[missingdistrict.missing_primary_count.gt(0)].boundary_stadtbezirk.value_counts().sort_index()
    discrepancy=join[join.name_discrepancy][['geo_code','geo_name','boundary_name']]
    definitions_table=definitions[['feature','original_german_name','english_name','definition','source_sheet','indicator_block','unit']]
    notes=f'''# Bremen Socioeconomic Inequality Atlas — 2024

## Purpose and section boundaries

This additive visual evidence package complements Section 2 V2 and answers RQ1 (neighborhood socioeconomic/demographic differences) and RQ2 (indicator usefulness). It reads the shared 2024 economic observations without changing them. It does not compute composites, TOPSIS, clustering, deprivation scores, official risk classes or disadvantage rankings. The cards are purposively selected economic examples, not a representative sample or a demographic atlas. Contextual demographic evidence remains in Section 2 V2.

## Data and definitions

Baseline: `{BASELINE}`, branch `analysis/section-2-v2`. Authoritative socioeconomic input: `data/processed/ortsteil_analysis_ready.csv`. There are 88 represented statistical geographic records, 79 complete cases, 79 valid unemployment observations, 79 employment observations and 84 SGB II observations. Codes are strings. All observations are 2024 percentages. The three denominators differ; unemployment is not the official all-civilian-labour-force unemployment rate. No missing observation is imputed or replaced with zero. Exact shared catalog definitions follow:

{markdown_table(definitions_table)}

Unemployment and receipt are relevant direct economic indicators with incomplete coverage and restricted definitions. Employment offers another labor-market perspective but excludes employment outside social insurance. These aggregate associations do not measure individual poverty, unmet benefit need or causation. All data, old output and Section 2 V2 hashes are checked before execution.

## Official boundary source and compatibility

Dataset: ATKIS - Verwaltungsgrenzen Land Bremen. Publisher and attribution: **Landesamt GeoInformation Bremen**. License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Source [official ISO metadata]({META}); [metadata page]({source['source_url']}); [WFS capabilities]({URLS['wfs_capabilities.xml']}); [official shapefile download]({URLS['verwaltungsgrenzen_hb.zip']}). Data were accessed on 10 October 2026. Raw responses and documentary evidence are frozen under `sources/`; URLs, CRS, format, dates and SHA-256 hashes are in `boundary_source_metadata.json`.

The metadata identifies a **dataset revision on 11 December 2024**, not an exact legal boundary-validity day. Metadata itself was updated in 2026; retrieval date is not the boundary date. GML coordinates are EPSG:25832 (ETRS89 / UTM zone 32N), used unchanged with equal map aspect and north-up orientation. This is an annual 2024 comparison, not proof that statistics and polygons have exactly identical reference days. Historical geometry compatibility is not established.

## Join and scope

The official Ortsteil WFS and ZIP DBF each contain **87** polygons; they agree on codes and names. WFS attributes incorrectly declare numberReturned=0 despite 87 actual member elements, so actual parsed records and independent DBF counts determine coverage. `sch_ot` ends in the shared three-digit code; independent `sch_ot_ags` confirms that suffix. Identifiers are unique and municipality codes are checked.

**Oberneuland exception:** the shared statistical table identifies 361, while the official polygon is Stadtteil `04011360`, absent from the Ortsteil layer. A named, explicit one-to-one crosswalk uses its unchanged official Stadtteil polygon. The [official administrative-division document]({LAW}) identifies Oberneuland as 361; the [2013 municipal proposal]({PROPOSAL}) explains the undivided area and its elevation to Stadtteil status. The proposal is documentary support, not a claim that a proposal is enacted law. The shared lookup has one statistical unit in this territory, and the current official layer has one Oberneuland polygon. This is a documented correspondence of an undivided area, not a generic suffix/name join between geographic levels or an invented polygon.

After that exception: **88/88 matched**, no unmatched polygon in the selected scope, no remaining unmatched socioeconomic record, no missing geometry. Three harmless name differences are reported rather than silently normalized:

{markdown_table(discrepancy)}

The scope is the 88 represented mainland statistical units. The separate overseas-port enclave (123) is absent from both the selected mainland layers and the socioeconomic master. These maps do not claim full coverage of all city territory or Land Bremen/Bremerhaven. Geometry checks cover CRS, finite closed nondegenerate rings, original vertices, multipart/hole rendering and coordinate area versus published area. No full topology/overlap certification is claimed. See `geographic_join_validation.csv`, `.json` and `.md`.

## Map classification and design

Maps A and B use the same extent and **shared fixed 5-percentage-point intervals**, from 0 to 35%, and the same sequential cividis palette. Every observed value is inside this range. Classes are [a,b), with the final upper bound included. Fixed shared breaks permit direct numerical rate comparison; they do not make the denominators interchangeable or constitute policy thresholds. Gray denotes missing observations: 9 for unemployment, 4 for SGB II. Both maps show all 88 mapped geographic records. Figures include boundary attribution, reporting year and boundary dataset revision year. At 300 DPI, labels are intentionally sparse; the supporting join CSV gives all geographic identities.

The bivariate map uses only the 79 paired observations to compute NumPy **linear quantiles at 1/3 and 2/3**. Unemployment cutpoints: {cuts['unemployment'][0]:.10f}% and {cuts['unemployment'][1]:.10f}%. SGB II cutpoints: {cuts['benefit_receipt'][0]:.10f}% and {cuts['benefit_receipt'][1]:.10f}%. Values equal to cutpoints belong to the lower class. Equal observed values would never be split. There are no repeated observed values, but **two observations per indicator lie exactly on its cutpoints**; they are assigned to the lower adjoining class. This gives marginal group sizes 27, 26 and 26, rather than splitting tied values or forcing equal counts. Repeated quantile boundaries would stop map production for explicit review; the script does not quietly reduce classes. The exported integer codes 0/1/2 identify categories, not scores. All 88 records remain in the export; nine missing either indicator have no assigned economic class and appear gray. The 3×3 legend separates the indicator dimensions; blue/teal–purple colors, text labels and the CSV support interpretation, without claiming accessibility for every color-vision condition.

## Economic indicator agreement and mapped descriptions

Spearman rho is **{classes['spearman_rho']:.16f}**, n=79, independently checked using ranked observations. **{same}/79 ({same/79*100:.2f}%)** occupy the same relative tertile for both indicators; **{different}/79** differ. This is relative economic-indicator agreement, not agreement among Section 4 methods and not external validation of deprivation. Changing class breaks may change apparent visual agreement.

{markdown_table(counts)}

Ohlenhof, in the official Bremen-West subdivision, has the highest observed unemployment (27.5409%) and SGB II receipt (34.6216%). Seehausen, in Bremen-Süd, has the lowest observed unemployment (2.5896%); In den Hufen, in Bremen-West, has the lowest available SGB II receipt (0.9901%) but missing unemployment. Thus similar overall association coexists with different coverage and denominators. In the bivariate map the upper/upper category contains {len(high)} observed units: {uppernames}. By official Stadtbezirk those upper/upper units are distributed as {highdistrict.to_dict()}. These categorical descriptions refer to actual mapped codes and official attributes. They establish neither formal spatial clustering nor spatial significance; no Moran's I, neighborhood weights or spatial hypothesis tests were computed. Large polygons are visually prominent regardless of population.

## Data blind spots and governance

All 88 geographic records are retained in `spatial_missingness_2024.csv`. There are 79 fully observed records, five missing two primary indicators, four missing all three, and none missing exactly one. The observed count and both independent completeness flags are checked. No selected geometry lacks a socioeconomic row; the map legend explicitly reports that count as zero.

{markdown_table(missing)}

By official subdivision, the nine incomplete units are {incompletedistrict.to_dict()}. Their exclusion reduces the scope of economic comparisons and could conceal evidence gaps from decision-support users. Missingness cannot be interpreted as favorable conditions or zero economic need. No reason for any missing observation is inferred from a neighborhood name, polygon area or land use. No population impact or missingness mechanism is estimated; denominator counts are unavailable.

## Evidence-card selection and findings

Selection is deterministic: observed unemployment maximum/minimum; observed SGB II maximum; deduplicate selected codes; first geographic code among records with all three economic values missing; and the only strictly opposite-side unemployment/SGB II median example among 79 complete observations. Ties at extrema use the lowest code. This produces four cards: Ohlenhof, Seehausen, Industriehäfen and Hastedt. The unemployment and SGB II maxima identify the same neighborhood. All panels share a 0–100% scale, with separate denominator explanations. Missing values are labeled and are not drawn as zero-length bars.

{markdown_table(display)}

Hastedt's unemployment is 11.5414%, above the complete-case median 10.9762%; its SGB II value is 12.4187%, below median 13.2323%. This is a modest, threshold-dependent contrast, not an exceptional risk classification; its bivariate tertile combination may still agree. Industriehäfen has no economic evidence for these three indicators, so its economic conditions cannot be inferred. All cards are observed examples and are not representative of Bremen's neighborhoods.

## Limitations and unresolved issues

The exact legal boundary reference day, exact indicator reference days and complete municipal denominator definitions remain unverified. The undivided Oberneuland crosswalk is explicit and should be reviewed if newer official definitions or geometry appear. No geometric topology certification is available with installed libraries; basic geometry and published area checks passed. The official boundary snapshot is archived, not a historical sequence. This evidence is for 2024, not current 2026 conditions. Aggregate rates cannot establish individual disadvantage, causal effects or resource-allocation priorities. No population weights, uncertainty intervals, formal spatial tests, composite index or rankings are produced. Median or tertile groups are sensitive to thresholds. Economic indicators overlap strongly. Demographic characteristics are not automatically deprivation; relevant context remains in V2. Missing data are not demonstrably random.

## Reproduction and preservation

Run from repository root with the existing environment:

```powershell
.\\.venv-section2\\Scripts\\python.exe -B src\\build_section2_atlas.py
```

Default reproduction is **offline**, using the archived sources and their pinned hashes. No package installation or GIS package is needed. Matplotlib renders original GML polygon coordinates without approximating boundaries. The `--fetch` option only downloads missing source snapshots; existing sources are never overwritten. A fresh WFS retrieval can differ in geometry IDs/timestamps/hash; it is not a substitute for the archived version and requires explicit review if pinned hashes differ. Source URLs are recorded for audit, not a promise that a live service reproduces byte-identical files later.

Outputs are staged and validated before publication; any differing existing atlas file prevents publication. Identical reruns leave outputs untouched. Shared tracked files, the old Section 2 files and all original V2 outputs are verified unchanged; source snapshots and inputs are hashed. `atlas_reproduction_manifest.json` records versions, hashes and validations. No changes are made to V2's original reproducibility manifest. Its frozen audit-time file inventory may differ from today's additive repository contents; the atlas has a separate manifest.

## Use in the report and other sections

Main report: use the side-by-side economic maps and missingness map; include the bivariate map only if there is space to explain its sample-relative classes. Presentation: side-by-side maps plus evidence cards provide clear observed contrasts. Supplement: individual maps, full join report, class counts and all CSVs. See `atlas_figure_captions.md`.

Section 1 can use documented contrasts and evidence gaps for problem framing. Section 3 can expose provenance, code crosswalks and missingness transparently. Section 4 receives unchanged primary inputs and warnings about indicator overlap; weighting, composite methods, TOPSIS, clustering and method-agreement evaluation remain its responsibilities.
'''
    captions=f'''# Atlas figure captions

1. **atlas_unemployment_2024.png** — Unemployment across Bremen's represented Ortsteil statistical units, 2024. Registered unemployed / (insured employees + registered unemployed), percent; 79 observed and 9 missing. Shared fixed 5-point classes, gray missing. This is a restricted quotient, not the official all-civilian-labour-force unemployment rate.
2. **atlas_sgbii_2024.png** — SGB II recipients / population under 65, percent, 2024; 84 observed and 4 missing. Same extent, class breaks and palette as unemployment; different denominator.
3. **atlas_economic_maps_side_by_side_2024.png** — Two economic rates across all 88 represented units, 2024; unemployment n=79 and SGB II n=84. Equal extents, 0–35% fixed 5-point classes. Missing is gray. Similar color does not make denominators equivalent.
4. **atlas_bivariate_economic_2024.png** — Relative sample tertiles of unemployment and under-65 SGB II receipt, 2024, n=79 paired observations. Gray indicates either indicator missing (9 units). The legend identifies both percentage dimensions; {same} observations share a tertile and {different} differ. Classes are not official risk/deprivation categories or a composite score. No formal spatial clustering is inferred.
5. **atlas_data_blind_spots_2024.png** — Number of missing primary economic indicators for every represented unit, 2024: 79 complete, 5 missing two, 4 missing all three. None missing one; zero polygons without a matching socioeconomic row. Unemployment, employment and SGB II have different denominators. Missingness is an evidence gap, not zero or a deprivation classification.
6. **atlas_neighborhood_evidence_cards_2024.png** — Four purposively selected Ortsteil examples, 2024, using the three primary economic percentages with distinct denominators and consistent 0–100% scales. Extrema deduplicated, first-code wholly missing case and sole strict median-disagreement case. Not representative. Explicit missing labels carry no economic interpretation.

Data for every figure: Statistisches Landesamt Bremen, supplied Datentabelle.xls, via shared ortsteil_analysis_ready.csv; exact worksheets/labels in atlas_methods_results.md. Boundaries for maps: Landesamt GeoInformation Bremen, ATKIS Verwaltungsgrenzen, CC BY 4.0; dataset revision 11 December 2024, retrieved 10 October 2026, EPSG:25832. All 88 represented mainland units are mapped; Oberneuland (statistical 361) uses the explicitly documented undivided Stadtteil polygon. Exact legal boundary-validity day is unverified; separate overseas-port enclave/Bremerhaven are outside this input scope. All figures are PNG at 300 DPI.
'''
    geodoc=f'''# Geographic join validation

Status: **PASS with explicit documented Oberneuland exception and reference-date limitations**.

Official Ortsteil WFS: 87 actual unique features, confirmed independently by the official shapefile DBF. Initial unmatched socioeconomic code: 361 Oberneuland. No unmatched polygon. Code suffixes were checked against the independent official AGS-style field. WFS numberReturned=0 is unreliable; actual member and DBF counts are used.

The undivided Oberneuland polygon is published as Stadtteil 04011360. The crosswalk to statistical 361 is individually documented using {LAW} and {PROPOSAL}. It is not a general conversion between levels. Final coverage: **88/88 matched**, no remaining unmatched records or missing geometry. The three name discrepancies are formatting/spelling variants:

{markdown_table(discrepancy)}

CRS: EPSG:25832. Official dataset revision: 11 December 2024; exact legal boundary-validity day remains unknown. Geometry tests: finite, closed, nondegenerate polygon rings, supported CRS/encoding, multipart/hole preservation, areas compared with official feature areas. No full topology/overlap certification. Full numeric/row evidence: geographic_join_validation.json and geographic_join_validation.csv.

Scope: 88 represented mainland statistical units, excluding a separately represented overseas-port enclave (123) and Bremerhaven. Map titles refer to this documented represented scope, not complete Land Bremen coverage.
'''
    return notes,captions,geodoc

def run():
    protected=protected_files()
    frame,definitions=load_data()
    polygons,join,geoval,source,extent=load_geography(frame)
    biv,counts,miss,cards,classes=build_tables(frame)
    with tempfile.TemporaryDirectory(prefix='bremen-atlas-') as tmp:
        stage=Path(tmp);rstage=stage/'reports';fstage=stage/'figures';rstage.mkdir();fstage.mkdir()
        tables={'geographic_join_validation.csv':join,'bivariate_classification_2024.csv':biv,
                'bivariate_class_counts.csv':counts,'spatial_missingness_2024.csv':miss,'neighborhood_card_data_2024.csv':cards}
        for n,table in tables.items(): table.to_csv(rstage/n,index=False,encoding='utf-8',float_format='%.17g')
        mapvalid=make_maps(fstage,frame,polygons,extent,biv,miss,classes)
        cardvalid=make_cards(fstage,cards)
        notes,captions,geodoc=documents(frame,definitions,join,geoval,source,biv,counts,miss,cards,classes)
        for n,t in [('atlas_methods_results.md',notes),('atlas_figure_captions.md',captions),('geographic_join_validation.md',geodoc)]:
            (rstage/n).write_text(t.strip()+'\n',encoding='utf-8')
        imvalid={}
        for n in MAP_FILES:
            with Image.open(fstage/n) as im:
                dpi=im.info.get('dpi')
                require(dpi and all(d>=299 for d in dpi) and min(im.size)>2000,'Figure resolution validation failed')
                require(im.getbbox() is not None,'Empty figure')
                imvalid[n]=dict(pixels=list(im.size),dpi=list(dpi))
            with Image.open(fstage/n) as verify_image:
                verify_image.verify()
        for n,table in tables.items():
            saved=pd.read_csv(rstage/n,dtype={'geo_code':str},float_precision='round_trip')
            require(len(saved)==len(table),'CSV row count changed')
            if 'geo_code' in saved:
                require(saved.geo_code.tolist()==table.geo_code.tolist() and saved.geo_code.is_unique,'CSV geographic identifiers changed')
            for feature in FEATURES:
                if feature in saved:
                    require(np.allclose(saved[feature],table[feature],rtol=0,atol=1e-13,equal_nan=True),'Figure/table value changed')
        require(len(biv)==len(miss)==88 and len(cards)==4,'Output record counts invalid')
        require(int(biv.unemployment_class.notna().sum())==79 and int(miss.shared_complete_case.sum())==79,'Output sample mismatch')
        require(miss.missing_primary_count.value_counts().to_dict()=={0:79,2:5,3:4},'Missingness count mismatch')
        validation=dict(branch='analysis/section-2-v2',commit=BASELINE,master_n=88,paired_n=79,
                        primary_valid_counts=frame[FEATURES].notna().sum().to_dict(),
                        missing_primary_count_distribution={str(k):int(v) for k,v in sorted(miss.missing_primary_count.value_counts().items())},
                        geographic_join=geoval,classification=classes,map_validation=mapvalid,card_validation=cardvalid,
                        figure_image_validation=imvalid,csv_roundtrip_verified=True,original_v2_manifest_and_outputs_verified=True,
                        original_v2_and_previous_files_unchanged=True,tracked_files_unchanged=True,protected_files_count=len(protected))
        for n,obj in [('geographic_join_validation.json',geoval),('boundary_source_metadata.json',source),
                      ('classification_breaks.json',classes),('atlas_validation.json',validation)]:
            (rstage/n).write_text(json_text(obj),encoding='utf-8')
        destinations={REPORT/p.name:p for p in rstage.iterdir()}
        destinations.update({FIGURES/p.name:p for p in fstage.iterdir()})
        manifest=dict(generator='src/build_section2_atlas.py',script_sha256=sha(Path(__file__)),baseline_commit=BASELINE,
                      versions=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,
                                    scipy=scipy.__version__,matplotlib=matplotlib.__version__),
                      reproduction_command='.\\.venv-section2\\Scripts\\python.exe -B src\\build_section2_atlas.py',
                      offline_reproduction_requires_frozen_sources=True,protected_input_hashes=protected,
                      outputs={rel(target):sha(p) for target,p in sorted(destinations.items())},validation=validation)
        (rstage/'atlas_reproduction_manifest.json').write_text(json_text(manifest),encoding='utf-8')
        destinations[REPORT/'atlas_reproduction_manifest.json']=rstage/'atlas_reproduction_manifest.json'
        require({rel(p) for p in destinations}==OWNED,'Unexpected output path inventory')
        # Preflight every collision before publishing any output, including manifest.
        for target,p in destinations.items():
            require(not target.exists() or sha(target)==sha(p),'Refusing to overwrite differing existing atlas output: '+rel(target))
        require(protected=={n:sha(ROOT/n) for n in protected},'Protected files changed before publication')
        for target,p in destinations.items():
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():
                with target.open('xb') as f, p.open('rb') as source_file:shutil.copyfileobj(source_file,f)
        require(protected=={n:sha(ROOT/n) for n in protected},'Protected files changed after publication')
        require(all(sha(target)==sha(p) for target,p in destinations.items()),'Published hash mismatch')
    print('PASS: 88 matched geographic records, explicit Oberneuland crosswalk; 79 paired observations; 6 figures; protected files unchanged.')
    print(json_text(classes))
    print(cards[['geo_code','geo_name',*FEATURES]].to_string(index=False))

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''): h.update(chunk)
    return h.hexdigest()

def fetch():
    SOURCES.mkdir(parents=True,exist_ok=True)
    for name,url in URLS.items():
        target=SOURCES/name
        if target.exists():
            if target.suffix in {'.xml','.gml'}: ET.parse(target)
            print('Retained existing source:',name)
            continue
        result=subprocess.run(['curl.exe','--fail','--silent','--show-error','--max-time','45',url],capture_output=True,check=True)
        if target.suffix in {'.xml','.gml'}:
            parsed=ET.fromstring(result.stdout)
            if 'Exception' in parsed.tag: raise ValueError(result.stdout[:2000])
        with target.open('xb') as f: f.write(result.stdout)
        print('Saved official source:',name,len(result.stdout),sha(target))

def inspect():
    doc=ET.parse(SOURCES/'ortsteile_bremen_epsg25832.gml').getroot()
    features=doc.findall('wfs:member/app:Ortsteile_Bremen',NS)
    props=[{c.tag.split('}')[-1]:c.text for c in f if not c.tag.endswith('geom')} for f in features]
    print('Actual members:',len(features),'WFS attributes:',doc.attrib)
    print(json.dumps(props,ensure_ascii=False,indent=2))
    m=ET.parse(SOURCES/'boundary_metadata.xml')
    for el in m.iter():
        if el.tag.split('}')[-1] in ['Date','DateTime','CharacterString','URL'] and el.text:
            print(el.tag.split('}')[-1],el.text)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--fetch',action='store_true')
    parser.add_argument('--inspect',action='store_true')
    args=parser.parse_args()
    if args.fetch: fetch()
    if args.inspect: inspect()
    if not args.fetch and not args.inspect:run()
