<template>
  <section class="architecture-panel">
    <header>
      <div>
        <span class="eyebrow">System map</span>
        <h2>Site architecture & shared modules</h2>
        <p>This registry documents navigation and reuse. It does not alter runtime routing.</p>
      </div>
      <div class="architecture-counts">
        <strong>{{ routeCount }}</strong><span>routes</span>
        <strong>{{ sharedModules.length }}</strong><span>shared modules</span>
      </div>
    </header>

    <div class="site-groups">
      <article v-for="group in siteGroups" :key="group.label">
        <h3>{{ group.label }}</h3>
        <p>{{ group.description }}</p>
        <div class="route-list">
          <NuxtLink v-for="node in group.nodes" :key="node.path" :to="node.path">
            <span>{{ node.label }}</span>
            <small :class="node.status.toLowerCase()">{{ node.status }}</small>
          </NuxtLink>
        </div>
      </article>
    </div>

    <div class="module-table-wrap">
      <table>
        <thead><tr><th>Shared module</th><th>Layer</th><th>Purpose</th><th>Consumers</th><th>Source</th></tr></thead>
        <tbody>
          <tr v-for="module in sharedModules" :key="module.name">
            <td><strong>{{ module.name }}</strong></td>
            <td><span class="layer-pill">{{ module.layer }}</span></td>
            <td>{{ module.purpose }}</td>
            <td>{{ module.consumers }}</td>
            <td><code>{{ module.source }}</code></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { sharedModules, siteGroups } from '~/config/siteArchitecture'

const routeCount = siteGroups.reduce((total, group) => total + group.nodes.length, 0)
</script>

<style scoped>
.architecture-panel { max-width: 1280px; margin: 16px auto 0; overflow: hidden; border: 1px solid var(--color-border); border-radius: 22px; background: #101010; }
.architecture-panel > header { display: flex; justify-content: space-between; gap: 24px; padding: 28px 30px; border-bottom: 1px solid var(--color-border); }
h2 { margin: 6px 0 0; color: var(--color-foreground); font-size: 28px; }
header p, article p { margin: 8px 0 0; color: var(--color-muted-text); }
.architecture-counts { display: grid; grid-template-columns: auto auto; align-content: center; gap: 2px 9px; text-align: right; }
.architecture-counts strong { color: var(--color-primary); font-family: "Fira Code", monospace; font-size: 22px; }
.architecture-counts span { align-self: center; color: var(--color-muted-text); font-size: 12px; font-weight: 800; text-transform: uppercase; }
.site-groups { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: var(--color-border); }
.site-groups article { padding: 24px; background: #111; }
h3 { margin: 0; color: var(--color-foreground); font-size: 20px; }
.route-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.route-list a { display: inline-flex; align-items: center; gap: 8px; border: 1px solid var(--color-border); border-radius: 999px; padding: 8px 11px; color: var(--color-foreground); text-decoration: none; font-size: 12px; font-weight: 850; }
.route-list a:hover { border-color: var(--color-primary); }
.route-list small { color: #85d39a; font-size: 9px; text-transform: uppercase; }
.route-list small.lab { color: var(--color-primary); }
.module-table-wrap { overflow-x: auto; border-top: 1px solid var(--color-border); }
table { width: 100%; min-width: 980px; border-collapse: collapse; }
th, td { border-bottom: 1px solid var(--color-border); padding: 14px 16px; color: var(--color-muted-text); text-align: left; font-size: 12px; }
th { color: var(--color-foreground); background: #151515; font-size: 10px; text-transform: uppercase; }
td strong { color: var(--color-foreground); }
code { color: #b5c5e6; font-size: 11px; }
.layer-pill { border: 1px solid color-mix(in srgb, var(--color-primary) 40%, var(--color-border)); border-radius: 999px; padding: 4px 7px; color: var(--color-primary); }
@media (max-width: 820px) { .architecture-panel > header { flex-direction: column; } .architecture-counts { align-self: start; text-align: left; } .site-groups { grid-template-columns: 1fr; } }
</style>
