<template>
  <span class="mlb-team-logo" :style="logoStyle">
    <img v-if="teamId && !failed" :src="logoUrl" :alt="decorative ? '' : `${normalizedTeam} logo`" @error="failed = true">
    <b v-else>{{ normalizedTeam || 'MLB' }}</b>
  </span>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{ team: string; size?: number; decorative?: boolean }>(), { size: 48, decorative: false })
const failed = ref(false)
const teamIds: Record<string, number> = { AZ:109,LAA:108,BAL:110,BOS:111,CHC:112,CIN:113,CLE:114,COL:115,DET:116,HOU:117,KC:118,LAD:119,WSH:120,NYM:121,ATH:133,PIT:134,SD:135,SEA:136,SF:137,STL:138,TB:139,TEX:140,TOR:141,MIN:142,PHI:143,ATL:144,CWS:145,MIA:146,NYY:147,MIL:158 }
const normalizedTeam = computed(() => props.team.trim().toUpperCase())
const teamId = computed(() => teamIds[normalizedTeam.value])
const logoUrl = computed(() => `https://www.mlbstatic.com/team-logos/${teamId.value}.svg`)
const logoStyle = computed(() => ({ width: `${props.size}px`, height: `${props.size}px` }))
watch(normalizedTeam, () => { failed.value = false })
</script>

<style scoped>
.mlb-team-logo{display:inline-grid;flex:none;place-items:center}.mlb-team-logo img{width:100%;height:100%;object-fit:contain}.mlb-team-logo b{font-size:12px;color:var(--color-muted-text)}
</style>
