<template>
  <g class="replay-batter-art" aria-hidden="true">
    <ellipse cx="91" cy="470" rx="68" ry="8" fill="#020b12" opacity=".5" />
    <g v-if="side==='left'" stroke="#102237" stroke-linejoin="round">
      <path d="M83 145 Q52 153 48 192 L39 267 60 290 116 280 142 225 130 169Z" fill="#e6edf1" stroke-width="3" />
      <path d="M47 190 62 181 72 243 58 279 39 267Z" fill="#a1b4c4" stroke="none" />
      <path d="M83 156 100 175 93 266" fill="none" stroke="#254e69" stroke-width="4" />
      <path d="M62 278 109 274 132 337 115 397 102 456 79 456 88 379 96 338 74 316 58 374 41 431 19 425 40 353Z" fill="#d9e4e9" stroke-width="3" />
      <path d="M72 312 59 371 40 431 23 425 42 354 59 294M103 339 99 392 85 453" fill="none" stroke="#849caf" stroke-width="8" />
      <path d="M18 420 41 430 38 453 13 463 0 456 3 445ZM80 447 104 447 124 464 122 473 77 473Z" fill="#172d47" stroke-width="3" />
      <path d="M7 456 32 453M84 465 117 466" stroke="#f2f7fa" stroke-width="5" />
      <path d="M63 126 67 155 92 164 104 145 98 120Z" fill="#b87752" stroke-width="2" />
      <path d="M62 71 Q87 46 109 72 L118 107 108 125 91 140 72 130 60 102Z" fill="#d6a080" stroke-width="2" />
      <path d="M105 90 118 98 113 105 105 105M95 115 108 116" fill="none" stroke="#8e5740" stroke-width="2" />
      <path d="M57 89 Q42 50 65 37 Q92 21 112 43 L118 78 138 84 139 92 104 94 90 75 68 82Z" fill="#173b55" stroke-width="3" />
      <path d="M62 46 Q84 31 103 48L108 70 79 61 61 76Z" fill="#2f607a" stroke="none" />
      <path d="M63 76 58 105 70 114 78 94Z" fill="#173b55" stroke-width="3" /><circle cx="69" cy="95" r="4" fill="#0a1c2d" />
      <path d="M100 86 110 88" stroke-width="3" /><path d="M89 168 113 171 123 207 140 170 155 179 139 222 115 231 96 206Z" fill="#f1f5f5" stroke-width="3" />
      <path d="M121 204 134 178 145 158 158 163 154 187 138 215Z" fill="#ca8e68" stroke-width="2" />
      <path d="M139 163 149 143 164 144 172 159 159 177 146 175Z" fill="#edf1e8" stroke-width="2" />
      <path d="M163 154 181 31" stroke="#714c31" stroke-width="12" stroke-linecap="round" /><path d="M164 134 178 35" stroke="#cfac78" stroke-width="6" stroke-linecap="round" />
      <path d="M143 171 151 151 165 155" fill="none" stroke="#76949c" stroke-width="3" /><path d="M58 270 111 269" stroke-width="9" /><rect x="77" y="265" width="13" height="10" rx="2" fill="#c4cbd0" stroke-width="2" />
    </g>
    <g v-else stroke="#102237" stroke-linejoin="round">
      <path d="M91 145 Q122 150 131 185 L142 259 125 285 67 282 40 226 51 170Z" fill="#e6edf1" stroke-width="3" />
      <path d="M128 183 112 180 108 242 125 279 142 259Z" fill="#9eb2c3" stroke="none" />
      <path d="M89 157 74 174 80 269" fill="none" stroke="#254e69" stroke-width="4" />
      <path d="M117 280 70 276 49 336 64 398 76 456 100 456 91 378 83 339 103 315 122 374 140 431 161 425 139 353Z" fill="#d9e4e9" stroke-width="3" />
      <path d="M105 313 121 372 142 430 158 426 138 353 120 297M76 340 80 394 93 451" fill="none" stroke="#849caf" stroke-width="8" />
      <path d="M142 425 163 418 177 446 179 456 162 463 138 453ZM76 447 99 448 104 472 59 473 56 465Z" fill="#172d47" stroke-width="3" />
      <path d="M147 454 173 456M64 466 98 465" stroke="#f2f7fa" stroke-width="5" />
      <path d="M114 125 109 154 86 163 73 146 79 121Z" fill="#b87752" stroke-width="2" />
      <path d="M114 70 Q88 48 67 73 L59 106 69 126 86 140 107 130 118 102Z" fill="#d6a080" stroke-width="2" />
      <path d="M73 91 58 98 65 105 73 105M69 116 83 115" fill="none" stroke="#8e5740" stroke-width="2" />
      <path d="M121 88 Q135 51 112 37 Q86 22 66 43 L60 77 40 83 39 92 74 94 90 75 111 82Z" fill="#173b55" stroke-width="3" />
      <path d="M113 47 Q91 32 73 48L67 70 96 62 114 76Z" fill="#2f607a" stroke="none" />
      <path d="M113 77 120 104 108 114 101 94Z" fill="#173b55" stroke-width="3" /><circle cx="110" cy="95" r="4" fill="#0a1c2d" />
      <path d="M69 89 79 87" stroke-width="3" /><path d="M88 168 65 171 53 206 38 172 23 179 40 222 64 231 82 205Z" fill="#f1f5f5" stroke-width="3" />
      <path d="M56 205 43 179 34 160 20 164 24 187 41 214Z" fill="#ca8e68" stroke-width="2" />
      <path d="M41 164 30 145 16 146 8 159 21 177 34 175Z" fill="#edf1e8" stroke-width="2" />
      <path d="M16 155 -3 32" stroke="#714c31" stroke-width="12" stroke-linecap="round" /><path d="M15 134 0 36" stroke="#cfac78" stroke-width="6" stroke-linecap="round" />
      <path d="M35 172 27 153 13 156" fill="none" stroke="#76949c" stroke-width="3" /><path d="M68 270 122 269" stroke-width="9" /><rect x="90" y="265" width="13" height="10" rx="2" fill="#c4cbd0" stroke-width="2" />
    </g>
  </g>
</template>
<script setup lang="ts">
// Two authored directional poses; generic presentation, never a real player's measured stance.
defineProps<{side:'left'|'right'}>()
</script>
