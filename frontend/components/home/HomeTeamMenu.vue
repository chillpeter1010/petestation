<template>
  <div
    class="home-team-menu"
    :class="{ 'home-team-menu--petehub': isPetehub }"
    @mouseenter="isOpen = true"
    @mouseleave="isOpen = false"
    @focusout="handleFocusOut"
  >
    <button
      type="button"
      aria-haspopup="menu"
      :aria-expanded="isOpen"
      aria-controls="home-team-menu"
      @click="isOpen = !isOpen"
      @keydown.esc="isOpen = false"
    >
      Teams
    </button>

    <div v-show="isOpen" id="home-team-menu" class="home-team-menu__panel" role="menu">
      <NuxtLink
        v-for="team in teams"
        :key="team.code"
        :to="`/teams/${team.code}`"
        role="menuitem"
        @click="isOpen = false"
      >
        <strong>{{ team.code }}</strong>
        <span>{{ team.name }}</span>
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
const isOpen = ref(false)
const { isPetehub } = useSiteBrand()

const teams = [
  { code: 'ATH', name: 'Athletics' },
  { code: 'AZ', name: 'Diamondbacks' },
  { code: 'ATL', name: 'Braves' },
  { code: 'BAL', name: 'Orioles' },
  { code: 'BOS', name: 'Red Sox' },
  { code: 'CHC', name: 'Cubs' },
  { code: 'CIN', name: 'Reds' },
  { code: 'CLE', name: 'Guardians' },
  { code: 'COL', name: 'Rockies' },
  { code: 'CWS', name: 'White Sox' },
  { code: 'DET', name: 'Tigers' },
  { code: 'HOU', name: 'Astros' },
  { code: 'KC', name: 'Royals' },
  { code: 'LAA', name: 'Angels' },
  { code: 'LAD', name: 'Dodgers' },
  { code: 'MIA', name: 'Marlins' },
  { code: 'MIL', name: 'Brewers' },
  { code: 'MIN', name: 'Twins' },
  { code: 'NYM', name: 'Mets' },
  { code: 'NYY', name: 'Yankees' },
  { code: 'PHI', name: 'Phillies' },
  { code: 'PIT', name: 'Pirates' },
  { code: 'SD', name: 'Padres' },
  { code: 'SEA', name: 'Mariners' },
  { code: 'SF', name: 'Giants' },
  { code: 'STL', name: 'Cardinals' },
  { code: 'TB', name: 'Rays' },
  { code: 'TEX', name: 'Rangers' },
  { code: 'TOR', name: 'Blue Jays' },
  { code: 'WSH', name: 'Nationals' }
]

function handleFocusOut(event: FocusEvent) {
  const container = event.currentTarget as HTMLElement
  if (!container.contains(event.relatedTarget as Node | null)) {
    isOpen.value = false
  }
}
</script>

<style scoped>
.home-team-menu {
  position: relative;
  z-index: 20;
  height: 41px;
  display: flex;
  align-items: center;
}

.home-team-menu > button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 41px;
  border: 0;
  border-bottom: 1px solid transparent;
  border-radius: 0;
  padding: 0;
  color: #d7d7d7;
  background: transparent;
  font-family: "Aptos", "Segoe UI", sans-serif;
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  transition: border-color .15s ease, color .15s ease;
}

.home-team-menu > button:hover,
.home-team-menu > button:focus-visible,
.home-team-menu > button[aria-expanded="true"] {
  color: var(--home-orange);
  border-color: var(--home-orange);
  background: transparent;
}

.home-team-menu--petehub {
  height: auto;
}

.home-team-menu--petehub > button {
  height: auto;
  min-height: 41px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  padding: 9px 15px;
  color: var(--home-muted);
  background: rgba(255, 255, 255, 0.045);
  font-family: inherit;
  font-size: inherit;
  font-weight: 900;
  line-height: normal;
}

.home-team-menu--petehub > button:hover,
.home-team-menu--petehub > button:focus-visible,
.home-team-menu--petehub > button[aria-expanded="true"] {
  color: #111;
  border-color: var(--home-orange);
  background: var(--home-orange);
}

.home-team-menu__panel {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  width: min(720px, calc(100vw - 36px));
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 5px;
  border: 1px solid rgba(255, 153, 0, 0.38);
  border-radius: 10px;
  padding: 12px;
  background: rgba(15, 15, 15, 0.98);
  box-shadow: 0 22px 70px rgba(0, 0, 0, 0.62);
}

.home-team-menu__panel::before {
  content: "";
  position: absolute;
  right: 25px;
  bottom: 100%;
  width: 80px;
  height: 11px;
}

.home-team-menu__panel a {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-radius: 6px;
  padding: 9px 10px;
  color: #f7f7f7;
  text-decoration: none;
}

.home-team-menu__panel a:hover,
.home-team-menu__panel a:focus-visible {
  color: #111111;
  background: var(--home-orange);
  outline: none;
}

.home-team-menu__panel strong {
  font-size: 13px;
}

.home-team-menu__panel span {
  overflow: hidden;
  color: #a9a9a9;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home-team-menu__panel a:hover span,
.home-team-menu__panel a:focus-visible span {
  color: rgba(17, 17, 17, 0.72);
}

@media (max-width: 720px) {
  .home-team-menu__panel {
    position: fixed;
    top: 126px;
    right: 18px;
    left: 18px;
    width: auto;
    max-height: calc(100vh - 148px);
    grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow-y: auto;
  }
}
</style>
