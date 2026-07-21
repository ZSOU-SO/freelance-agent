<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink class="brand" to="/" aria-label="freelance-agent 首页">
        <span>FA</span>
        <div>
          <strong>freelance-agent</strong>
          <small>需求分析与报价助手</small>
        </div>
      </RouterLink>
      <nav class="app-nav"><RouterLink to="/">需求分析</RouterLink><RouterLink to="/cases">历史案例</RouterLink></nav>
    </header>
    <RouterView />
  </div>
</template>
