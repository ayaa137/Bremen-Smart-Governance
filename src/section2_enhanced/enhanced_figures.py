"""Refined copies only: verified arrays and polygon paths, deterministic PNG/PDF/SVG."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import matplotlib
import analyze_section2_v2 as v2
import build_section2_atlas as atlas

def render(stage,frame,complete,context,polygons,extent,biv,miss,cards,classes,correlations,loo,summary):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'svg.hashsalt':'bremen-section2-enhanced-2024'})
    originals=atlas.MAP_FILES
    atlas.MAP_FILES=[n.replace('atlas_','enhanced_atlas_',1) for n in originals]
    original_save=Figure.savefig;original_cmap=plt.get_cmap
    artifacts=[]
    def cmap(name,*args,**kwargs):return original_cmap('cividis_r' if name=='cividis' else name,*args,**kwargs)
    def save(fig,path,*args,**kwargs):
        path=Path(path)
        if path.suffix!='.png':return original_save(fig,path,*args,**kwargs)
        if 'bivariate' in path.name:
            fig.text(.065,.122,'Cutpoints (%): unemployment 8.5398 / 14.1290; SGB II 10.2200 / 18.0283.',fontsize=9)
            fig.text(.065,.103,'Same tertile: 65/79 (82.3%); classes are relative to the observed sample.',fontsize=9)
        kwargs['metadata']={'Software':'Bremen Section 2 enhanced; deterministic export'}
        original_save(fig,path,*args,**kwargs);artifacts.append(path.name)
        for extension,metadata in [('pdf',{'Creator':'Bremen Section 2 enhanced','CreationDate':None,'ModDate':None}),
                                   ('svg',{'Creator':'Bremen Section 2 enhanced','Date':None})]:
            dest=path.with_suffix('.'+extension)
            original_save(fig,dest,metadata=metadata,facecolor='white');artifacts.append(dest.name)
    Figure.savefig=save;plt.get_cmap=cmap
    try:
        mapvalid=atlas.make_maps(stage,frame,polygons,extent,biv,miss,classes)
        mapvalid['univariate_palette']='cividis_r: higher rates darker; indicator values, not deprivation classifications'
        evidence_cards(stage,cards)
        corr=correlations[correlations['sample'].eq('complete')]
        quadrant,qcounts,qinfo=v2.quadrants(complete)
        files,selected,grid=v2.draw_figures(stage,complete,frame,context,corr,quadrant,qinfo)
        contextual(stage,context)
        robustness(stage,loo,summary)
    finally:
        Figure.savefig=original_save;plt.get_cmap=original_cmap;atlas.MAP_FILES=originals
    return artifacts,mapvalid,selected,grid

def evidence_cards(stage,cards):
    fig,axes=plt.subplots(2,2,figsize=(15,12));fig.subplots_adjust(left=.10,right=.97,bottom=.28,top=.83,hspace=.92,wspace=.4)
    fig.suptitle('Selected neighborhood evidence · Bremen Ortsteil · 2024',x=.035,ha='left',fontsize=19,y=.975)
    fig.text(.035,.932,'Extrema, an evidence gap and a median contrast; deliberately selected, not representative.',fontsize=11)
    reasons={'443':'Unemployment and SGB II maxima','261':'Unemployment minimum',
             '122':'First-code case with three missing indicators','382':'Only strict median-disagreement case'}
    colors=['#176d8e','#237c68','#b45639']
    for ax,row in zip(axes.flat,cards.itertuples()):
        title=f'{row.geo_name} ({row.geo_code})'
        ax.set_title(title,loc='left',fontweight='bold',fontsize=14,pad=25,
                     color='#684898' if row.geo_code=='382' else '#202020')
        ax.text(0,1.03,reasons[row.geo_code],transform=ax.transAxes,fontsize=9)
        ax.set(xlim=(0,100),ylim=(-.6,2.65),xlabel='Observed percentage; distinct denominators')
        ax.set_yticks([2,1,0],['Unemployment','Employment','SGB II under 65'],fontsize=9)
        ax.set_xticks([0,25,50,75,100]);ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True)
        for y,feature,c in zip([2,1,0],atlas.FEATURES,colors):
            value=getattr(row,feature)
            if pd.isna(value):ax.text(3,y,'MISSING — not zero',va='center',fontsize=10,color='#666666')
            else:
                ax.barh(y,value,height=.48,color=c);ax.text(value+1.5,y,f'{value:.1f}%',va='center',fontsize=10)
        import textwrap
        statement=row.interpretation
        if row.geo_code=='382':statement='Unemployment 11.5% > median 11.0%; SGB II 12.4% < median 13.2%. This contrast depends on median thresholds.'
        ax.text(0,-.36,'\n'.join(textwrap.wrap(statement,67)),transform=ax.transAxes,fontsize=9,va='top')
    fig.text(.035,.123,'Denominators: unemployed / (insured employees + unemployed); insured employees / population aged 15–<65;',fontsize=9)
    fig.text(.035,.103,'SGB II recipients / population under 65. Three observed indicators for each card except Industriehäfen (0/3).',fontsize=9)
    fig.text(.035,.064,atlas.DATA_SOURCE,fontsize=8)
    fig.text(.035,.041,'Displayed to one decimal; supporting CSV preserves source precision. Hastedt is a descriptive contrast, not an official risk category.',fontsize=8)
    fig.text(.035,.019,'Missing values are labeled, not drawn as zero. Selected areas do not represent all neighborhoods.',fontsize=8)
    fig.savefig(stage/'enhanced_atlas_neighborhood_evidence_cards_2024.png',dpi=300,facecolor='white');plt.close(fig)

def contextual(stage,context):
    fig,axes=plt.subplots(1,3,figsize=(14,5.5));fig.subplots_adjust(left=.065,right=.985,bottom=.25,top=.77,wspace=.30)
    for ax,f,c in zip(axes,['child_benefits','single_parents','income_median'],['#b45639','#684898','#237c68']):
        data=context[f].value.dropna().to_numpy();bins=np.histogram_bin_edges(data,bins='fd')
        n,_,_=ax.hist(data,bins=bins,color=c,edgecolor='white')
        assert n.sum()==len(data)
        median=float(np.median(data));ax.axvline(median,ls='--',color='#252525',lw=1.4)
        title={'child_benefits':'SGB II receipt among under-15s\n2024 · n=84',
               'single_parents':'Single-parent household share\n2024 · n=83',
               'income_median':'Historical taxpayer income\n2020 only · n=84'}[f]
        label={'child_benefits':'Recipients under 15 / population under 15 (%)',
               'single_parents':'Single-parent / main-residence\nhouseholds with children (%)',
               'income_median':'Median income per taxpayer (€1,000)'}[f]
        ax.set(title=title,xlabel=label,ylabel='Ortsteile (count)');ax.grid(axis='y',alpha=.18)
        ax.text(.98,.95,f'Median {median:.1f}',ha='right',va='top',transform=ax.transAxes,fontsize=9,
                bbox={'fc':'white','ec':'#dddddd','alpha':.95})
    fig.suptitle('Contextual variation · Bremen Ortsteil · separate periods and populations',x=.035,ha='left',fontsize=15)
    fig.text(.035,.088,atlas.DATA_SOURCE+' Context: selected_indicators_long.csv.',fontsize=8)
    fig.text(.035,.059,'Available observations per indicator; missing values excluded from each histogram, never imputed. Original source precision retained.',fontsize=8)
    fig.text(.035,.031,'Family structure is not intrinsic deprivation. Child receipt overlaps under-65 receipt; 2020 taxpayer income is not 2024 household disposable income.',fontsize=8)
    fig.savefig(stage/'contextual_distributions_separate_periods.png',dpi=300,facecolor='white');plt.close(fig)

def robustness(stage,loo,summary):
    fig,axes=plt.subplots(1,2,figsize=(12,5.4));fig.subplots_adjust(left=.075,right=.985,top=.78,bottom=.25,wspace=.33)
    for ax,measure,baseline,name in zip(axes,['spearman_rho','kendall_tau_b'],[summary['baseline_rho'],summary['baseline_tau_b']],['Spearman rho','Kendall tau-b']):
        values=loo[measure].to_numpy();n,_,_=ax.hist(values,bins=12,color='#176d8e',ec='white')
        assert n.sum()==79
        ax.axvline(baseline,color='#b45639',lw=2,ls='--',label='All 79 cases')
        ax.set(title=name,xlabel='Correlation after excluding one Ortsteil (n=78)',ylabel='Omissions (count)')
        ax.ticklabel_format(axis='x',style='plain',useOffset=False);ax.grid(axis='y',alpha=.18);ax.legend(fontsize=9)
    fig.suptitle('Unemployment–SGB II sensitivity · Bremen Ortsteil · 2024',x=.035,ha='left',fontsize=15)
    fig.text(.035,.10,atlas.DATA_SOURCE,fontsize=8)
    fig.text(.035,.07,'All 79 omissions retained. Horizontal axes are narrowly scaled and differ; these are descriptive sensitivity checks, not confidence intervals.',fontsize=8)
    fig.text(.035,.04,'Distinct indicator denominators; no observations deleted from the analysis and no causal interpretation.',fontsize=8)
    fig.savefig(stage/'correlation_leave_one_out_sensitivity_2024.png',dpi=300,facecolor='white');plt.close(fig)
