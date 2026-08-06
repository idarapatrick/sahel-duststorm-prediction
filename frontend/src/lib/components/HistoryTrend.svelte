<script lang="ts">
	import type { HistoricalSnapshot } from '$lib/types';
	export let items: HistoricalSnapshot[] = [];
	$: ordered = [...items].sort((a, b) => a.recordedAt.localeCompare(b.recordedAt)).slice(-10);
	$: values = ordered.map((item) => item.probability * 100);
	$: average = values.length ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length) : 0;
	$: minimum = values.length ? Math.round(Math.min(...values)) : 0;
	$: maximum = values.length ? Math.round(Math.max(...values)) : 0;
	$: change = values.length > 1 ? Math.round(values.at(-1)! - values[0]) : 0;
	$: volatility = values.length > 1 ? Math.round(values.slice(1).reduce((sum, value, index) => sum + Math.abs(value - values[index]), 0) / (values.length - 1)) : 0;
	$: points = ordered.map((item, index) => ({ ...item, x: ordered.length === 1 ? 50 : 5 + index * (90 / (ordered.length - 1)), y: 95 - item.probability * 90 }));
	$: path = points.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ');
	$: trendText = change > 5 ? 'Risk increased' : change < -5 ? 'Risk decreased' : 'Risk remained broadly stable';
</script>

<section class="analysis glass" aria-labelledby="history-analysis-title">
	<header><div><p>History analysis</p><h2 id="history-analysis-title">How dust risk changed</h2></div><span class:up={change > 0} class:down={change < 0}>{change > 0 ? '+' : ''}{change} points</span></header>
	<div class="summary">
		<div><small>Average</small><strong>{average}%</strong></div>
		<div><small>Lowest</small><strong>{minimum}%</strong></div>
		<div><small>Highest</small><strong>{maximum}%</strong></div>
		<div><small>Typical change</small><strong>{volatility} pts</strong></div>
	</div>
	{#if points.length > 1}
		<div class="chart"><svg viewBox="0 0 100 100" role="img" aria-label={`${trendText} by ${Math.abs(change)} percentage points across ${points.length} predictions`} preserveAspectRatio="none"><line x1="5" y1="5" x2="95" y2="5"/><line x1="5" y1="50" x2="95" y2="50"/><line x1="5" y1="95" x2="95" y2="95"/><path d={path}/>{#each points as point}<circle cx={point.x} cy={point.y} r="1.7"><title>{new Date(point.recordedAt).toLocaleString()}: {Math.round(point.probability * 100)}%</title></circle>{/each}</svg><div class="scale"><span>100%</span><span>50%</span><span>0%</span></div></div>
		<p class="interpretation"><strong>{trendText}.</strong> The latest stored result is {Math.round(values.at(-1) ?? 0)}%, compared with {Math.round(values[0] ?? 0)}% at the beginning of this period.</p>
	{:else}<p class="empty">At least two stored predictions are needed for change analysis.</p>{/if}
</section>

<style>
	.analysis{margin:20px 0;padding:22px;border-radius:24px}.analysis header{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.analysis header p{margin:0 0 4px;color:var(--text-secondary);font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em}.analysis h2{margin:0;font-size:clamp(1.2rem,3vw,1.75rem)}header>span{padding:7px 10px;border-radius:999px;background:var(--surface-muted);font-size:.78rem;font-weight:800}header>span.up{color:var(--red)}header>span.down{color:var(--green)}.summary{margin:20px 0;display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--border);border-radius:18px;overflow:hidden}.summary div{padding:15px;border-right:1px solid var(--border)}.summary div:last-child{border:0}.summary small,.summary strong{display:block}.summary small{color:var(--text-secondary);font-size:.7rem}.summary strong{margin-top:5px;font-size:1.35rem}.chart{position:relative;padding-left:34px}.chart svg{width:100%;height:190px;overflow:visible}.chart line{stroke:var(--border);stroke-width:.5;stroke-dasharray:2 2}.chart path{fill:none;stroke:var(--blue);stroke-width:2.3;vector-effect:non-scaling-stroke}.chart circle{fill:var(--surface-solid);stroke:var(--blue);stroke-width:1.3;vector-effect:non-scaling-stroke}.scale{position:absolute;inset:0 auto 0 0;display:flex;flex-direction:column;justify-content:space-between;color:var(--text-secondary);font-size:.64rem}.interpretation{margin:14px 0 0;color:var(--text-secondary);line-height:1.55}.interpretation strong{color:var(--text)}.empty{color:var(--text-secondary)}@media(max-width:620px){.analysis{padding:16px}.summary{grid-template-columns:1fr 1fr}.summary div:nth-child(2){border-right:0}.summary div:nth-child(-n+2){border-bottom:1px solid var(--border)}.chart svg{height:145px}}
</style>
