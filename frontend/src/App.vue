<template>
  <div id="app-root">
    <el-container class="app-container">
      <el-header class="app-header">
        <div class="header-left">
          <el-icon :size="22" color="#409EFF"><Document /></el-icon>
          <span class="header-title">试卷批改系统</span>
        </div>
        <el-menu mode="horizontal" :default-active="currentRoute" router class="header-menu">
          <el-menu-item index="/">
            <el-icon><EditPen /></el-icon>
            <span>批改</span>
          </el-menu-item>
          <el-menu-item index="/history">
            <el-icon><Clock /></el-icon>
            <span>历史</span>
          </el-menu-item>
          <el-menu-item index="/prompts">
            <el-icon><Setting /></el-icon>
            <span>提示词</span>
          </el-menu-item>
        </el-menu>
      </el-header>
      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Document, EditPen, Clock, Setting } from '@element-plus/icons-vue'

const route = useRoute()
const currentRoute = computed(() => route.path)
</script>
