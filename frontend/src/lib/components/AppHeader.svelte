<script lang="ts">
	import { Search, Moon, Sun, ChevronDown, Wind } from 'lucide-svelte';
	import type { Location } from '$lib/types';
	import { createEventDispatcher, onMount } from 'svelte';

	export let selected: Location;
	export let locations: Location[] = [];
	export let online = true;
	const dispatch = createEventDispatcher<{ select: Location }>();
	let query = '';
	let dark = false;
	let open = false;

	onMount(() => dark = document.documentElement.dataset.theme === 'dark');
	$: filtered = locations.filter((x) => `${x.name} ${x.country}`.toLowerCase().includes(query.toLowerCase()));

	function toggleTheme() {
		dark = !dark;
		document.documentElement.dataset.theme = dark ? 'dark' : 'light';
		localStorage.setItem('sahelwatch-theme', dark ? 'dark' : 'light');
	}
	function choose(location: Location) { selected = location; dispatch('select', location); open = false; query = ''; }
</script>

<header class="header glass">
	<a class="brand" href="/" aria-label="SahelWatch home">
		<span class="mark"><Wind size={21} strokeWidth={2.2} /></span>
		<span><strong>SahelWatch</strong><small>Dust intelligence, hours ahead</small></span>
	</a>
	<div class="search-wrap">
		<label class="search">
			<Search size={18} aria-hidden="true" />
			<span class="sr-only">Search a covered Sahel community</span>
			<input bind:value={query} on:focus={() => open = true} placeholder="Search a city, town or village" autocomplete="off" />
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
		<button class="location" on:click={() => open = !open} aria-expanded={open}><span>{selected.name}</span><ChevronDown size={16} /></button>
		<button class="icon" on:click={toggleTheme} aria-label={dark ? 'Use light theme' : 'Use dark theme'}>{#if dark}<Sun size={20} />{:else}<Moon size={20} />{/if}</button>
	</div>
</header>

<style>
	.header { position: relative; z-index: 20; min-height: 72px; padding: 10px 12px; border-radius: 26px; display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 12px; }
	.brand { min-width: 0; display: flex; gap: 10px; align-items: center; }
	.mark { width: 42px; height: 42px; border-radius: 14px; display: grid; place-items: center; color: white; background: linear-gradient(145deg, #147df5, #0057d6); box-shadow: 0 8px 22px rgba(0,122,255,.25); }
	.brand strong, .brand small { display: block; }
	.brand strong { font-size: 1.08rem; letter-spacing: -.025em; }
	.brand small { margin-top: 2px; max-width: 190px; overflow: hidden; color: var(--text-secondary); font-size: .7rem; white-space: nowrap; text-overflow: ellipsis; }
	.search-wrap { position: absolute; top: 14px; left: 50%; width: min(34vw, 390px); transform: translateX(-50%); }
	.search { height: 44px; padding: 0 14px; display: flex; align-items: center; gap: 9px; border: 1px solid var(--border); border-radius: var(--radius-pill); color: var(--text-tertiary); background: var(--surface-muted); }
	.search:focus-within { border-color: var(--blue); box-shadow: 0 0 0 3px var(--ring); }
	.search input { width: 100%; border: 0; outline: 0; color: var(--text); background: transparent; font-size: .86rem; }
	.results { position: absolute; top: 52px; width: 100%; max-height: min(420px, 65vh); padding: 8px; overflow-y: auto; overscroll-behavior: contain; border-radius: 20px; }
	.results button { width: 100%; min-height: 46px; padding: 8px 10px; display: flex; align-items: center; justify-content: space-between; border: 0; border-radius: 13px; background: transparent; cursor: pointer; }
	.results button:hover { background: var(--surface-muted); }
	.results small, .results p { color: var(--text-secondary); }
	.results p { padding: 8px; font-size: .85rem; }
	.actions { display: flex; align-items: center; gap: 6px; }
	.status, .location { min-height: 44px; display: flex; align-items: center; gap: 8px; border: 0; border-radius: var(--radius-pill); background: var(--surface-muted); font-size: .78rem; font-weight: 600; }
	.status { padding: 0 13px; color: var(--text-secondary); }
	.status i { width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 0 5px color-mix(in srgb, var(--green) 14%, transparent); animation: breathe 2.4s ease-in-out infinite; }
	.status i.offline { background: var(--orange); box-shadow: none; animation: none; }
	.location { padding: 0 12px; cursor: pointer; }
	.icon { width: 44px; height: 44px; display: grid; place-items: center; border: 0; border-radius: 50%; background: var(--surface-muted); cursor: pointer; }
	@keyframes breathe { 50% { box-shadow: 0 0 0 8px color-mix(in srgb, var(--green) 2%, transparent); } }
	@media (max-width: 820px) { .header { grid-template-columns: 1fr auto; } .search-wrap { position: relative; top: auto; left: auto; grid-column: 1 / -1; grid-row: 2; width: 100%; transform: none; } .status { display: none; } }
	@media (max-width: 470px) { .brand small, .location span { display: none; } .location { width: 44px; justify-content: center; } }
</style>
