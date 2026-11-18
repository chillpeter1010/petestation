<template>
  <section class="release-guide" aria-label="Static arm angle and recorded release">
    <header>
      <div><h4>Arm angle · {{ pitcherName }}</h4><small>{{ row.pitch_name || 'Pitch' }} · PA {{ row.at_bat_number ?? '—' }} / Pitch {{ row.pitch_number ?? '—' }} · {{ guide.hand || '?' }}HP</small></div>
      <label>Perspective<select v-model="perspective"><option value="front">Front · catcher</option><option value="back">Back · pitcher</option></select></label>
    </header>
    <div class="release-layout">
      <svg viewBox="0 0 400 340" role="img" :aria-label="description">
        <title>{{ description }}</title>
        <rect width="400" height="340" rx="12" fill="#edf4f5" />
        <g fill="none" stroke="#c4d3d9" stroke-width="1">
          <path v-for="height in [0,2,4,6,8,10]" :key="height" :d="`M30 ${295-height*25}H370`" />
          <path d="M200 35V295" stroke-dasharray="4 5" />
        </g>
        <g fill="#435a66" font-size="12"><text v-for="height in [0,2,4,6,8,10]" :key="height" x="6" :y="299-height*25">{{ height }}′</text><text x="132" y="326">Release X · feet</text><text x="36" y="313">{{ perspective==='front' ? '−6' : '+6' }}</text><text x="195" y="313">0</text><text x="344" y="313">{{ perspective==='front' ? '+6' : '−6' }}</text></g>
        <g v-if="guide.shoulder && guide.centreX!=null" aria-hidden="true">
          <g :transform="`translate(${guide.centreX} ${guide.shoulder.y})`" fill="#b0c7cc" stroke="#7e9ca5" stroke-width="1.5">
            <circle cy="-20" r="11" />
            <path :d="`M-13 -7Q0 -13 13 -7L18 47L9 58H-9L-18 47Z`" />
            <path :d="`M-9 54L-15 ${Math.max(70,(295-guide.shoulder.y)*.92)}L-4 ${Math.max(74,295-guide.shoulder.y)}L3 58L7 ${Math.max(74,295-guide.shoulder.y)}L18 ${Math.max(70,(295-guide.shoulder.y)*.92)}L9 54Z`" />
          </g>
          <path :d="`M${guide.shoulder.x} ${guide.shoulder.y}h${guide.mirror*(guide.hand==='R'?-1:1)*62}`" stroke="#8398a2" stroke-width="2" stroke-dasharray="5 4" />
          <path :d="`M${guide.shoulder.x} ${guide.shoulder.y}L${guide.release!.x} ${guide.release!.y}`" stroke="#101923" stroke-width="8" stroke-linecap="round" />
          <circle :cx="guide.shoulder.x" :cy="guide.shoulder.y" r="4" fill="#fff" stroke="#101923" stroke-width="2" />
        </g>
        <g v-if="guide.release"><circle :cx="guide.release.x" :cy="guide.release.y" r="7" fill="#ffbd36" stroke="#5d3a00" stroke-width="2" /><text :x="guide.release.x+11" :y="guide.release.y-11" fill="#694200" font-size="13" font-weight="700">Release</text></g>
        <text v-else x="65" y="170" fill="#435a66" font-size="15">Release X / Z unavailable</text>
      </svg>
      <div class="release-data">
        <strong class="angle">{{ format(guide.angle,1,'°') }}</strong><span>Arm angle · 0° horizontal / 90° overhead</span>
        <dl><div v-for="field in fields" :key="field.label"><dt>{{ field.label }}</dt><dd>{{ format(field.value,2,' ft') }}</dd></div></dl>
        <svg v-if="guide.y!=null" viewBox="0 0 360 85" role="img" aria-label="Recorded release Y relative to the pitching rubber">
          <path d="M18 48H342" stroke="#94acb6" stroke-width="2" /><path d="M342 37V59M18 37V59" stroke="#e9f0f5" stroke-width="3" />
          <circle :cx="18+guide.y/60.5*324" cy="48" r="6" fill="#ffbd36" />
          <g fill="#dce8ee" font-size="12"><text x="18" y="23">Plate origin · Y 0</text><text x="237" y="23">Rubber · 60.5 ft</text><text :x="Math.min(270,Math.max(20,18+guide.y/60.5*324-60))" y="78">Release Y {{ guide.y.toFixed(2) }} ft</text></g>
        </svg>
        <p v-if="guide.angle==null || !guide.hand">Angle guide unavailable: recorded arm angle and throwing hand are required.</p>
      </div>
    </div>
    <details><summary>Diagram / source guide</summary><p>Gold is the recorded ball release X / Z; the black direction uses this pitch’s arm angle. The pale body, shoulder and 2-ft line length are schematic, not measured joints or a reconstructed pose. Front / back only changes the view. Release Y and extension are independent source fields; extension is not stride length. Negative angles are retained; missing values are not filled.</p><a href="https://baseballsavant.mlb.com/leaderboard/pitcher-arm-angles" target="_blank" rel="noopener noreferrer">Savant arm-angle definition ↗</a></details>
  </section>
</template>
<script setup lang="ts">
import { pitchReleaseGuide, type ReleasePerspective } from '~/utils/pitchReleaseGuide'
const props=defineProps<{row:Record<string,unknown>;pitcherName:string}>()
const perspective=ref<ReleasePerspective>('front')
const guide=computed(()=>pitchReleaseGuide(props.row,perspective.value))
const format=(value:number|null,digits:number,suffix:string)=>value==null?'unavailable':value.toFixed(digits)+suffix
const fields=computed(()=>[{label:'Release X',value:guide.value.x},{label:'Release Y',value:guide.value.y},{label:'Release height / Z',value:guide.value.z},{label:'Extension',value:guide.value.extension}])
const description=computed(()=>`${props.pitcherName}, ${guide.value.hand||'unknown hand'}, arm angle ${format(guide.value.angle,1,' degrees')}, release height ${format(guide.value.z,2,' feet')}. ${perspective.value} view. Schematic body, recorded ball position.`)
</script>
<style scoped>
.release-guide{border:1px solid var(--color-border,#455769);border-radius:12px;padding:14px;background:var(--color-surface,#14212c);color:var(--color-foreground,#e8eef5)}header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}h4{margin:0 0 5px;font-size:18px}small{color:var(--color-muted-text,#a3b8c9)}label{display:grid;gap:5px;font-size:12px}select{font:inherit;color:inherit;background:var(--color-background,#101c27);padding:9px;border:1px solid var(--color-border,#455769);border-radius:6px;min-height:42px}.release-layout{display:grid;grid-template-columns:minmax(240px,400px) minmax(220px,1fr);gap:20px;margin:14px 0;align-items:center}svg{width:100%;display:block}.release-data{display:grid;gap:8px;min-width:0}.angle{font-size:34px;color:#ffc861}dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}dt{font-size:12px;color:var(--color-muted-text,#a3b8c9)}dd{margin:4px 0 0;font-size:17px;font-weight:750;font-variant-numeric:tabular-nums}summary{cursor:pointer;min-height:28px}details p{line-height:1.6}a{color:inherit}select:focus-visible,summary:focus-visible{outline:2px solid #ffbd36;outline-offset:3px}@media(max-width:650px){.release-layout{grid-template-columns:1fr}.release-layout>svg{max-width:400px;justify-self:center}}
</style>
