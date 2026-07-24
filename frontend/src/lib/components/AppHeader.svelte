<script lang="ts">
	import { Search, Moon, Sun, ChevronDown, Wind } from 'lucide-svelte';
	import type { Location } from '$lib/types';
	import { createEventDispatcher, onMount } from 'svelte';

	export let selected: Location;
	export let locations: Location[] = [];
	export let online = true;
	const dispatch = createEventDispatcher<{ select: Location; theme: 'light' | 'dark' }>();
	let query = '';
	let dark = false;
	let open = false;
	let headerElement: HTMLElement;

	function closeOutside(event: PointerEvent) {
		if (open && headerElement && !headerElement.contains(event.target as Node)) open = false;
	}
	onMount(() => {
		dark = document.documentElement.dataset.theme === 'dark';
		document.addEventListener('pointerdown', closeOutside);
		return () => document.removeEventListener('pointerdown', closeOutside);
	});
	$: filtered = locations.filter((x) => `${x.name} ${x.country}`.toLowerCase().includes(query.toLowerCase()));

	function toggleTheme() {
		dark = !dark;
		const theme = dark ? 'dark' : 'light';
		document.documentElement.dataset.theme = theme;
		localStorage.setItem('sahelwatch-theme', theme);
		dispatch('theme', theme);
	}
	function choose(location: Location) { selected = location; dispatch('select', location); open = false; query = ''; }
</script>

<header class="header glass" bind:this={headerElement}>
	<a class="brand" href="/" aria-label="SahelWatch home">
		<span class="mark"><Wind size={21} strokeWidth={2.2} /></span>
		<span><strong>SahelWatch</strong><small>Dust intelligence, hours ahead</small></span>
	</a>
	<div class="search-wrap" class:open>
		<label class="search">
			<Search size={18} aria-hidden="true" />
			<span class="sr-only">Search a covered Sahel community</span>
			<input bind:value={query} on:focus={() => open = true} on:keydown={(event) => { if (event.key === 'Escape') open = false; }} placeholder="Search a city, town or village" autocomplete="off" />
		</label>
		{#if open}
			<div class="results glass">
				{#each filtered as location}
					<button on:click={() => choose(location)}><span>{location.name}</span><small>{location.country}{location.placeType ? ` · ${location.placeType}` : ''}{location.coverageStatus === 'provisional' ? ' · checks continuing' : ''}</small></button>
				{:else}<p>No covered community found</p>{/each}
			</div>
		{/if}
	</div>
	<div class="actions">
		<div class="status" title={online ? 'Live updates connected' : 'Live updates unavailable'}><i class:offline={!online}></i><span>{online ? 'Live updates' : 'Updates offline'}</span></div>
		<button class="location" on:click={() => open = !open} aria-label={`Change forecast location. Current location: ${selected.name}`} aria-expanded={open} aria-haspopup="listbox"><span>{selected.name}</span><ChevronDown size={16} /></button>
		<button class="icon" on:click={toggleTheme} aria-label={dark ? 'Use light theme' : 'Use dark theme'}>{#if dark}<Sun size={20} />{:else}<Moon size={20} />{/if}</button>
	</div>
</header>

<style>
	.header { position: relative; z-index: 20; min-height: 72px; padding: 10px 12px; border-radius: 26px; display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 12px; }
	.brand { min-width: 0; display: flex; gap: 10px; align-items: center; }
	.mark { width: 42px; height: 42px; border: 1px solid rgba(255,255,255,.48); border-radius: 14px; display: grid; place-items: center; color: var(--on-brand); background: linear-gradient(145deg, #759fc6, var(--brand-strong)); box-shadow: 0 10px 28px color-mix(in srgb,var(--blue) 38%,transparent),inset 0 1px rgba(255,255,255,.62); }
	.brand strong, .brand small { display: block; }
	.brand strong { font-size: 1.08rem; letter-spacing: -.025em; }
	.brand small { margin-top: 2px; max-width: 190px; overflow: hidden; color: var(--text-secondary); font-size: .7rem; white-space: nowrap; text-overflow: ellipsis; }
	.search-wrap { position: absolute; top: 14px; left: 50%; width: min(34vw, 390px); transform: translateX(-50%); }
	.search { height: 44px; padding: 0 14px; display: flex; align-items: center; gap: 9px; border: 1px solid var(--glass-border); border-radius: var(--radius-pill); color: var(--text-tertiary); background:color-mix(in srgb,var(--surface-solid) 46%,transparent); box-shadow:inset 0 1px rgba(255,255,255,.38); backdrop-filter:blur(22px) saturate(170%); }
	.search:focus-within { border-color: var(--blue); box-shadow: 0 0 0 3px var(--ring); }
	.search input { width: 100%; border: 0; outline: 0; color: var(--text); background: transparent; font-size: .86rem; }
	.results { position: absolute; top: 52px; width: 100%; max-height: min(420px, 65vh); padding: 8px; overflow-y: auto; overscroll-behavior: contain; border-radius: 20px; }
	.results button { width: 100%; min-height: 46px; padding: 8px 10px; display: flex; align-items: center; justify-content: space-between; border: 0; border-radius: 13px; background: transparent; cursor: pointer; }
	.results button:hover { background: var(--surface-muted); }
	.results small, .results p { color: var(--text-secondary); }
	.results p { padding: 8px; font-size: .85rem; }
	.actions { display: flex; align-items: center; gap: 6px; }
	.status, .location { min-height: 44px; display: flex; align-items: center; gap: 8px; border: 1px solid color-mix(in srgb,var(--glass-border) 70%,transparent); border-radius: var(--radius-pill); background:color-mix(in srgb,var(--surface-solid) 34%,transparent); box-shadow:inset 0 1px rgba(255,255,255,.32); backdrop-filter:blur(20px) saturate(170%); font-size: .78rem; font-weight: 600; }
	.status { padding: 0 13px; color: var(--text-secondary); }
	.status i { width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 0 5px color-mix(in srgb, var(--green) 14%, transparent); animation: breathe 2.4s ease-in-out infinite; }
	.status i.offline { background: var(--orange); box-shadow: none; animation: none; }
	.location { padding: 0 12px; cursor: pointer; }
	.icon { width: 44px; height: 44px; display: grid; place-items: center; border: 1px solid color-mix(in srgb,var(--glass-border) 70%,transparent); border-radius: 50%; background:color-mix(in srgb,var(--surface-solid) 34%,transparent); box-shadow:inset 0 1px rgba(255,255,255,.32); backdrop-filter:blur(20px); cursor: pointer; }
	@keyframes breathe { 50% { box-shadow: 0 0 0 8px color-mix(in srgb, var(--green) 2%, transparent); } }
	@media (max-width: 820px) {
		.header { min-height: 64px; grid-template-columns: 1fr auto; }
		.search-wrap { display: none; position: absolute; z-index: 40; top: 72px; right: 0; left: 0; width: 100%; transform: none; }
		.search-wrap.open { display: block; }
		.search { background: color-mix(in srgb,var(--surface-solid) 92%,transparent); box-shadow: var(--shadow-md); backdrop-filter: blur(28px) saturate(155%); -webkit-backdrop-filter: blur(28px) saturate(155%); }
		.results { max-height: min(520px, calc(100dvh - 150px)); background: color-mix(in srgb,var(--surface-solid) 96%,transparent); border-color:var(--glass-border); box-shadow:var(--shadow-lg); }
		.status { display: none; }
	}
	@media (max-width: 470px) { .brand small, .location span { display: none; } .location { width: 44px; justify-content: center; } }
</style>
