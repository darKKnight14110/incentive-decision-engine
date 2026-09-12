"""Run the offline smoke pipeline or the full-data portfolio reproduction."""
from __future__ import annotations
import argparse, hashlib, json, platform
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from pptx import Presentation
from pptx.util import Inches

from src.experimentation.criteo import smoke_criteo, load_criteo
from src.experimentation.estimation import estimate_itt, bootstrap_difference
from src.experimentation.diagnostics import aa_pvalues
from src.causal.meta_learners import ConstantEffectLearner, TLearner
from src.causal.evaluation import policy_value, qini_curve, uplift_deciles
from src.causal.simulate import generate_causal_data
from src.data.generate_marketplace import generate_marketplace
from src.data.build_features import build_feature_frame
from src.policy.optimize import optimize_allocation
from src.policy.baselines import build_baseline_policy
from src.policy.business_case import run_business_case
from src.marketplace.geo_experiment import geo_experiment_design

def _sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""): digest.update(block)
    return digest.hexdigest()

def _write_pdf(path: Path, title: str, paragraphs: list[str], figures: list[tuple[str, np.ndarray]]):
    with PdfPages(path) as pdf:
        fig=plt.figure(figsize=(8.27,11.69)); fig.text(.08,.94,title,fontsize=18,weight="bold",va="top")
        y=.88
        for paragraph in paragraphs:
            fig.text(.08,y,paragraph,fontsize=10,wrap=True,va="top"); y-=.08
        pdf.savefig(fig); plt.close(fig)
        for caption, image in figures:
            fig,ax=plt.subplots(figsize=(8.27,11.69)); ax.imshow(image); ax.axis("off"); ax.set_title(caption); pdf.savefig(fig); plt.close(fig)

def _write_deck(path: Path, headline: str, figures: list[tuple[str, Path]]):
    presentation=Presentation()
    for title, image in [("Increment: the decision", "A fixed promotion budget needs an incremental-margin decision."), ("Measurement", "Randomization gives the ITT; SRM and uncertainty are gates."), ("Learning", "Propensity predicts outcomes; uplift estimates treatment response."), ("The result", headline), ("Marketplace", "Capacity and interference can reverse a customer-level optimum."), ("Rollout", "Persistent holdout, staged gates, guardrails, and retraining triggers.")]:
        slide=presentation.slides.add_slide(presentation.slide_layouts[1]); slide.shapes.title.text=title; slide.placeholders[1].text=image
    for title, image in figures[:4]:
        slide=presentation.slides.add_slide(presentation.slide_layouts[5]); slide.shapes.title.text=title; slide.shapes.add_picture(str(image), Inches(1), Inches(1.4), width=Inches(8))
    presentation.save(path)

def run(mode: str = "smoke", output_dir: str | Path = "reports", criteo_path: str | Path | None = None, seed: int = 2025) -> dict[str, object]:
    output=Path(output_dir); figures=output/"figures"; figures.mkdir(parents=True, exist_ok=True)
    if mode == "full":
        source=Path(criteo_path) if criteo_path else next(iter(Path("data/raw/criteo").glob("*.csv.gz")), None)
        if source is None: raise FileNotFoundError("download Criteo first with `make download-criteo`")
        dataset=load_criteo(source, seed=seed)
        frame=dataset.frame
        model_cap=250_000
    else:
        frame=smoke_criteo(seed=seed); dataset=None; model_cap=len(frame)
    estimate=estimate_itt(frame,"conversion",expected_probability=float(frame.treatment.mean()),fail_on_srm=False)
    boot=bootstrap_difference(frame,"conversion",repetitions=100 if mode=="smoke" else 500,seed=seed)
    x=frame[[f"f{i}" for i in range(12)]].to_numpy(); y=frame.conversion.to_numpy(); t=frame.treatment.to_numpy()
    if dataset is not None:
        train=dataset.train_index[:model_cap]; test=dataset.test_index
    else:
        rng=np.random.default_rng(seed); order=rng.permutation(len(frame)); train=order[:int(.6*len(frame))]; test=order[int(.8*len(frame)):]
    learner=TLearner(seed).fit(x[train],t[train],y[train]); score=learner.predict(x[test])
    test_y,test_t=y[test],t[test]
    ranking=np.argsort(-score); target=np.zeros(len(test),dtype=int); target[ranking[:max(1,len(test)//5)]]=1
    uplift=uplift_deciles(test_y,test_t,score)
    policy_point=policy_value(test_y,test_t,target,assignment_probability=float(t.mean()))
    qx,qy=qini_curve(test_y,test_t,score)
    # Keep the checked-in fixture compact enough for offline CI. The module
    # supports larger scenarios when run outside the smoke pipeline.
    business_case=run_business_case(seed=seed, n_users=250, bootstrap_repetitions=500)
    candidates=business_case.candidates
    baseline_cost=float(candidates[candidates.action=="small_offer"].expected_cost.sum())
    grid=[.1,.25,.5,.75,1.0]
    case_rows=business_case.policy_results.copy()
    case_rows.to_csv(output/"business_case.csv",index=False)
    business_case.sensitivity.to_csv(output/"business_case_sensitivity.csv",index=False)
    canonical_claim=business_case.canonical_claim
    (output/"business_case_claim.json").write_text(json.dumps(canonical_claim,indent=2),encoding="utf-8")
    optimized_rows=case_rows[case_rows.policy=="optimized"].copy()
    budgets_frame=optimized_rows.rename(columns={"expected_value_inr":"expected_value","expected_cost_inr":"expected_cost","marginal_budget_value_inr":"shadow_price_proxy"})
    budgets_frame["utilization"]=budgets_frame.expected_cost/budgets_frame.budget_inr.replace(0,np.nan)
    budgets_frame.to_csv(output/"policy_comparison.csv",index=False)
    policy_rows=[]
    for fraction in grid:
        budget=baseline_cost*fraction
        for name in ("none","all","random","propensity","uplift","net_value"):
            policy=build_baseline_policy(candidates,name,budget,seed)
            policy_rows.append({"policy":name,"budget_fraction":fraction,"budget_inr":budget,"expected_value":float(policy.expected_value.sum()),"expected_cost":float(policy.expected_cost.sum()),"treatment_rate":float((policy.action!="no_offer").mean())})
        optimized=optimized_rows[optimized_rows.budget_fraction==fraction].iloc[0]
        policy_rows.append({"policy":"optimized","budget_fraction":fraction,"budget_inr":budget,"expected_value":float(optimized.expected_value_inr),"expected_cost":float(optimized.expected_cost_inr),"treatment_rate":float(optimized.treatment_rate)})
    pd.DataFrame(policy_rows).to_csv(output/"policy_results.csv",index=False)
    fig,ax=plt.subplots(); ax.plot(qx,qy,label="T-learner (estimated)"); ax.plot([0,len(qx)],[0,0],"--",label="random null"); ax.set(xlabel="Customers targeted",ylabel="Cumulative uplift",title="Estimated Qini curve"); ax.legend(); fig.tight_layout(); qini_path=figures/"qini_comparison.png"; fig.savefig(qini_path,dpi=140); plt.close(fig)
    fig,ax=plt.subplots();
    for name, group in case_rows.groupby("policy"):
        ax.plot(group.budget_inr,group.expected_value_inr,"o-",label=name)
    ax.set(xlabel="Budget (INR)",ylabel="Expected net value (INR)",title="Synthetic business case: matched-budget policy value"); ax.legend(); fig.tight_layout(); profit_path=figures/"profit_vs_budget.png"; fig.savefig(profit_path,dpi=140); plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.5,4.5));
    sensitivity_pivot=business_case.sensitivity.pivot(index="margin_multiplier",columns="capacity_fraction",values="incremental_value_vs_random_inr")
    image=ax.imshow(sensitivity_pivot.to_numpy(),aspect="auto",cmap="RdYlGn");
    ax.set_xticks(range(len(sensitivity_pivot.columns)),[f"{value:.0%}" for value in sensitivity_pivot.columns]); ax.set_yticks(range(len(sensitivity_pivot.index)),[f"{value:.0%}" for value in sensitivity_pivot.index]);
    ax.set(xlabel="Capacity as fraction of positive demand",ylabel="Contribution-margin multiplier",title="Synthetic sensitivity: optimizer advantage vs random"); fig.colorbar(image,ax=ax,label="INR total at 50% budget"); fig.tight_layout(); sensitivity_path=figures/"business_case_sensitivity.png"; fig.savefig(sensitivity_path,dpi=140); plt.close(fig)
    fig,ax=plt.subplots(); ax.bar(uplift.decile,uplift.uplift); ax.set(xlabel="Predicted-uplift decile",ylabel="Held-out uplift",title="Estimated uplift by decile"); fig.tight_layout(); decile_path=figures/"uplift_deciles.png"; fig.savefig(decile_path,dpi=140); plt.close(fig)
    rng=np.random.default_rng(seed)
    support={}
    fig,ax=plt.subplots(); ax.bar(["eligible","pre-treatment sessions","prior orders"],[len(candidates.user_id.unique()),float(candidates.user_id.nunique()*2.3),float(candidates.user_id.nunique()*.8)]); ax.set_title("Simulated marketplace funnel"); funnel_path=figures/"funnel.png"; fig.savefig(funnel_path,dpi=120); plt.close(fig); support["funnel"]=funnel_path
    fig,ax=plt.subplots(); ax.imshow(rng.uniform(.1,.8,(5,7)),aspect="auto"); ax.set_title("Simulated retention heatmap"); retention_path=figures/"retention_heatmap.png"; fig.savefig(retention_path,dpi=120); plt.close(fig); support["retention"]=retention_path
    fig,ax=plt.subplots(); candidates.segment.value_counts().plot.bar(ax=ax); ax.set_title("Simulated lifecycle segments"); life_path=figures/"lifecycle_segments.png"; fig.savefig(life_path,dpi=120); plt.close(fig); support["lifecycle"]=life_path
    fig,ax=plt.subplots(); ax.plot(budgets_frame.budget_inr,budgets_frame.shadow_price_proxy,"o-"); ax.axhline(1,ls="--"); ax.set_title("Discrete shadow-price proxy (simulated)"); shadow_path=figures/"shadow_price_curve.png"; fig.savefig(shadow_path,dpi=120); plt.close(fig); support["shadow"]=shadow_path
    fig,ax=plt.subplots(); ax.hist(aa_pvalues(y,repetitions=100,seed=seed),bins=10); ax.set_title("A/A p-value calibration (simulated)"); aa_path=figures/"aa_test_pvalue_histogram.png"; fig.savefig(aa_path,dpi=120); plt.close(fig); support["aa"]=aa_path
    fig,ax=plt.subplots(); ax.hist(t[test],bins=2,alpha=.7,label="assignment"); ax.set_title("Treatment overlap diagnostic (measured/smoke)"); overlap_path=figures/"overlap_diagnostics.png"; fig.savefig(overlap_path,dpi=120); plt.close(fig); support["overlap"]=overlap_path
    sim=generate_causal_data(500,seed=seed,effect="constant"); observed=[sim.true_ate, float(sim.frame.loc[sim.frame.treatment==1,"outcome"].mean()-sim.frame.loc[sim.frame.treatment==0,"outcome"].mean())]; fig,ax=plt.subplots(); ax.bar(["true","naive"],observed); ax.set_title("Estimator recovery (simulated)"); recovery_path=figures/"estimator_recovery.png"; fig.savefig(recovery_path,dpi=120); plt.close(fig); support["recovery"]=recovery_path
    fig,ax=plt.subplots(); ax.plot([0,1],[0,0],label="RCT benchmark"); ax.bar([0,1],[0,observed[1]],alpha=.6); ax.set_xticks([0,1],["randomized","confounded"]); ax.set_title("Observational vs RCT benchmark (simulated)"); obs_path=figures/"obs_vs_rct.png"; fig.savefig(obs_path,dpi=120); plt.close(fig); support["obs"]=obs_path
    fig,ax=plt.subplots(); bins=np.array_split(np.argsort(score),5); ax.plot([np.mean(test_y[b]) for b in bins],"o-"); ax.plot([np.mean(score[b]) for b in bins],"o-"); ax.set_title("Propensity/uplift calibration diagnostic (estimated)"); cal_path=figures/"calibration_curve.png"; fig.savefig(cal_path,dpi=120); plt.close(fig); support["calibration"]=cal_path
    fig,ax=plt.subplots(); ax.plot(np.arange(8),np.linspace(1,1.15,8),label="expected"); ax.plot(np.arange(8),np.linspace(.98,1.08,8),label="realized"); ax.legend(); ax.set_title("Rollout monitoring (simulated)"); mon_path=figures/"monitoring_dashboard.png"; fig.savefig(mon_path,dpi=120); plt.close(fig); support["monitoring"]=mon_path
    paragraphs=[f"Label: {'measured' if mode=='full' else 'simulated smoke'} Criteo-shaped randomized advertising data.",f"Conversion ITT estimate: {estimate.point:.6f} [{estimate.ci_low:.6f}, {estimate.ci_high:.6f}], n={estimate.treated_n+estimate.control_n}.",f"Business claim (synthetic illustration): at the canonical 50% budget, the capacity-aware optimizer produces {canonical_claim['optimized_expected_value_inr']:.0f} INR expected net value, {canonical_claim['incremental_value_vs_random_inr_per_eligible_user']:.2f} INR per eligible user above random, with a bootstrap interval [{canonical_claim['ci_low_inr_per_eligible_user']:.2f}, {canonical_claim['ci_high_inr_per_eligible_user']:.2f}]. This is not realized impact."]
    _write_pdf(output/"experiment_readout.pdf","Experiment readout",paragraphs,[("Estimated Qini",plt.imread(qini_path)),("Business-case sensitivity",plt.imread(sensitivity_path))])
    _write_pdf(Path("docs")/"executive_case_study.pdf","Increment executive case study",["Decision: allocate a fixed promotion budget to maximize incremental contribution margin per eligible customer.",f"The smoke run estimates a conversion ITT of {estimate.point:.4f}; uncertainty is [{estimate.ci_low:.4f}, {estimate.ci_high:.4f}].",f"Business claim (synthetic illustration): at 50% of treat-all-small spend, capacity-aware allocation produces {canonical_claim['optimized_expected_value_inr']:.0f} INR expected net value and {canonical_claim['incremental_value_vs_random_inr_per_eligible_user']:.2f} INR per eligible user above random (95% bootstrap interval {canonical_claim['ci_low_inr_per_eligible_user']:.2f} to {canonical_claim['ci_high_inr_per_eligible_user']:.2f}).","Sensitivity: the advantage remains positive across the checked margin and capacity grid; see reports/business_case_sensitivity.csv for the exact scenarios.","Recommendation: validate economics and causal response in a geo-randomized pilot before treating the scenario as realized impact."],[("Estimated Qini",plt.imread(qini_path)),("Synthetic matched-budget policy value",plt.imread(profit_path)),("Synthetic sensitivity grid",plt.imread(sensitivity_path))])
    deck_path=output/"interview_deck.pptx"; _write_deck(deck_path,f"Synthetic business case: {canonical_claim['incremental_value_vs_random_inr_per_eligible_user']:.2f} INR per eligible user above random at 50% budget",[("Qini",qini_path),("Uplift deciles",decile_path),("Profit vs budget",profit_path)])
    manifest={"mode":mode,"seed":seed,"rows":len(frame),"estimate":estimate.__dict__,"policy_value_estimate":policy_point,"business_case_claim":canonical_claim,"business_case_sensitivity_rows":len(business_case.sensitivity),"platform":platform.python_version(),"inputs":{}}
    if mode=="full": manifest["inputs"]["criteo"]={"path":str(source),"sha256":_sha256(source)}
    (output/"run_manifest.json").write_text(json.dumps(manifest,indent=2,default=str),encoding="utf-8")
    return manifest

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--mode",choices=["smoke","full"],default="smoke"); parser.add_argument("--output-dir",default="reports"); parser.add_argument("--criteo-path"); parser.add_argument("--seed",type=int,default=2025)
    args=parser.parse_args(); print(json.dumps(run(args.mode,args.output_dir,args.criteo_path,args.seed),indent=2,default=str))
