<script lang="ts">
	import '$lib/styles/global.css';
	import { onMount } from 'svelte';

	onMount(() => {
		const saved = localStorage.getItem('sahelwatch-theme');
		if (saved === 'dark') document.documentElement.dataset.theme = 'dark';
	});
</script>

<svelte:head>
	<link rel="icon" href="/favicon.svg" />
</svelte:head>

<slot />
