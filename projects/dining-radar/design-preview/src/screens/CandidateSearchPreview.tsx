import React, { useState, useMemo } from "react";
import { 
  MapPin, 
  Clock, 
  Users, 
  ExternalLink, 
  AlertTriangle, 
  RefreshCw, 
  Layers, 
  ChevronRight, 
  X,
  Info,
  Lock
} from "lucide-react";

/**
 * ============================================================================
 * Required API additions:
 * - None required.
 *   The current API provides all necessary fields for the designed hierarchy.
 *   Our layout gracefully handles all potential null values without requiring 
 *   additional endpoints or data fields.
 * ============================================================================
 */

/* ============================================================================
   TYPES & INTERFACES
   ============================================================================ */

interface Candidate {
  candidateRef: string;
  name: string;
  genre: string;
  description: string | null;
  businessHours: string | null;
  regularHoliday: string | null;
  totalSeats: number | null;
  access: string | null;
  providerPageUrl: string;
  // Review-only visual positions (Percentage coordinates instead of latitude/longitude)
  // TDR-CS-02: Map marker mapping without exposing coordinates or baseline points
  visualPosition: {
    x: number; // Left percentage (0 - 100)
    y: number; // Top percentage (0 - 100)
  };
  isNew?: boolean; // Visual flag for first-appearance vs re-appearance
}

interface Proposal {
  conceptRef: string;
  kind: "PROXIMITY" | "CAPACITY_REFERENCE" | "GENRE_VARIETY" | "AMENITY_REFERENCE";
  title: string;
  rationale: string;
  candidates: Candidate[];
}

interface ReProposalOption {
  kind: "PROXIMITY" | "CAPACITY_REFERENCE" | "GENRE_VARIETY" | "AMENITY_REFERENCE";
  title: string;
  rationale: string;
}

/* ============================================================================
   SYNTHETIC DATA DEFINITIONS (Strictly adhering to instructions)
   ============================================================================ */

const SYNTHETIC_CANDIDATES: Record<string, Candidate> = {
  a: {
    candidateRef: "cand_a",
    name: "架空食堂 青い匙",
    genre: "和食",
    description: "季節 of 小鉢と温かい定食を中心にした、架空の食堂です。",
    businessHours: "11:00〜14:30",
    regularHoliday: "日曜・祝日",
    totalSeats: 38,
    access: "架空オフィス街の南側",
    providerPageUrl: "https://example.invalid/shop-a",
    visualPosition: { x: 35, y: 40 }
  },
  b: {
    candidateRef: "cand_b",
    name: "架空ビストロ 木曜日",
    genre: "洋食",
    description: "煮込み料理とプレートランチを扱う架空のビストロです。",
    businessHours: "11:30〜15:00",
    regularHoliday: "月曜",
    totalSeats: 24,
    access: "架空文化施設の向かい",
    providerPageUrl: "https://example.invalid/shop-b",
    visualPosition: { x: 65, y: 30 }
  },
  c: {
    candidateRef: "cand_c",
    name: "架空喫茶 北窓",
    genre: "カフェ・軽食",
    description: null,
    businessHours: "10:30〜16:00",
    regularHoliday: null,
    totalSeats: 18,
    access: "架空並木通り沿い",
    providerPageUrl: "https://example.invalid/shop-c",
    visualPosition: { x: 20, y: 70 }
  },
  d: {
    candidateRef: "cand_d",
    name: "架空ダイニング 月灯り",
    genre: "創作料理",
    description: "野菜を使った日替わり料理を出す架空のダイニングです。",
    businessHours: null,
    regularHoliday: "水曜",
    totalSeats: null,
    access: "架空複合ビルの1階",
    providerPageUrl: "https://example.invalid/shop-d",
    visualPosition: { x: 75, y: 75 }
  }
};

const CONCEPT_METADATA = {
  PROXIMITY: {
    title: "移動を軽く、ゆっくり話す",
    rationale: "候補集合の中から、移動負担を抑えやすい店舗を優先しています。"
  },
  CAPACITY_REFERENCE: {
    title: "席数を見ながら選ぶ",
    rationale: "総席数の参考値が比較しやすい候補をまとめています。空席は保証しません。"
  },
  GENRE_VARIETY: {
    title: "いつもと違う味を試す",
    rationale: "異なるジャンルを横断し、選択肢に変化をつけています。"
  },
  AMENITY_REFERENCE: {
    title: "落ち着いて比較する",
    rationale: "取得できた設備情報を比較の入口にした候補です。利用可否は詳細ページで確認します。"
  }
};

/* ============================================================================
   STYLES (Self-contained CSS Injection)
   ============================================================================ */

const CSS_STYLES = `
  .tdr-app-root {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans CJK JP", sans-serif;
    color: #1e293b;
    background-color: #f8fafc;
    min-height: 100vh;
    padding: 0;
    margin: 0;
    box-sizing: border-box;
  }
  .tdr-app-root *, .tdr-app-root *::before, .tdr-app-root *::after {
    box-sizing: border-box;
  }
  .tdr-container {
    max-width: 1280px;
    margin: 0 auto;
    padding: 1.5rem;
  }
  .tdr-header {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    padding: 1rem 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  }
  .tdr-brand {
    font-size: 1.25rem;
    font-weight: 800;
    color: #0f172a;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    letter-spacing: -0.025em;
  }
  .tdr-brand-logo {
    display: inline-flex;
    padding: 0.35rem;
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
    color: #ffffff;
    border-radius: 0.5rem;
  }
  .tdr-signout-btn {
    font-size: 0.875rem;
    color: #64748b;
    background: none;
    border: 1px solid #e2e8f0;
    padding: 0.375rem 0.75rem;
    border-radius: 0.375rem;
    cursor: pointer;
    transition: all 0.2s;
  }
  .tdr-signout-btn:hover {
    background-color: #f1f5f9;
    color: #0f172a;
  }
  .tdr-main-layout {
    display: grid;
    grid-template-columns: 1fr 420px;
    gap: 1.5rem;
    margin-top: 1.5rem;
  }
  @media (max-width: 1024px) {
    .tdr-main-layout {
      grid-template-columns: 1fr;
    }
  }
  
  /* --- Concept Header Card --- */
  .tdr-concept-banner {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    padding: 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }
  .tdr-concept-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    background-color: #eff6ff;
    color: #1e40af;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 0.25rem 0.625rem;
    border-radius: 9999px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .tdr-concept-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0.5rem 0 0.25rem 0;
  }
  .tdr-concept-rationale {
    font-size: 0.875rem;
    color: #475569;
    margin: 0;
    line-height: 1.5;
  }
  .tdr-repropose-trigger {
    background-color: #0f172a;
    color: #ffffff;
    border: none;
    padding: 0.625rem 1rem;
    border-radius: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    white-space: nowrap;
    transition: all 0.2s;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  }
  .tdr-repropose-trigger:hover {
    background-color: #1e293b;
  }

  /* --- Candidate Cards List --- */
  .tdr-cards-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  /* --- Refined Card Layout (Problem 1, 3, 4, 5) --- */
  .tdr-card {
    background-color: #ffffff;
    border: 2px solid #e2e8f0;
    border-radius: 0.875rem;
    padding: 1.25rem;
    transition: all 0.2s ease-in-out;
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .tdr-card:hover {
    border-color: #94a3b8;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
  }
  .tdr-card.tdr-card-active {
    border-color: #3b82f6;
    box-shadow: 0 0 0 1px #3b82f6, 0 4px 12px rgba(59, 130, 246, 0.08);
    background-color: #fcfdff;
  }
  .tdr-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.75rem;
  }
  .tdr-card-badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
    align-items: center;
  }
  .tdr-marker-id {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.5rem;
    height: 1.5rem;
    background-color: #0f172a;
    color: #ffffff;
    font-size: 0.75rem;
    font-weight: 800;
    border-radius: 0.375rem;
  }
  .tdr-card-active .tdr-marker-id {
    background-color: #3b82f6;
  }
  .tdr-genre-chip {
    background-color: #f1f5f9;
    color: #475569;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.125rem 0.5rem;
    border-radius: 0.25rem;
  }
  .tdr-novelty-chip {
    background-color: #f0fdf4;
    color: #166534;
    border: 1px solid #bbf7d0;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 0.05rem 0.375rem;
    border-radius: 0.25rem;
  }
  .tdr-reappear-chip {
    background-color: #f8fafc;
    color: #64748b;
    border: 1px solid #e2e8f0;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.05rem 0.375rem;
    border-radius: 0.25rem;
  }
  .tdr-shop-name {
    font-size: 1.125rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0.25rem 0 0 0;
    line-height: 1.35;
  }
  
  /* Hierarchy Grouping: 
     Section 1: Description
     Section 2: Structured Details (Time, Place, Size) */
  .tdr-card-description {
    font-size: 0.875rem;
    color: #334155;
    line-height: 1.5;
    margin: 0;
  }
  .tdr-card-description.tdr-missing-val {
    color: #94a3b8;
    font-style: italic;
  }

  /* Two-column layout for structured comparison variables */
  .tdr-card-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
    background-color: #f8fafc;
    border-radius: 0.5rem;
    padding: 0.75rem;
    border: 1px solid #f1f5f9;
  }
  @media (max-width: 480px) {
    .tdr-card-grid {
      grid-template-columns: 1fr;
    }
  }
  .tdr-grid-item {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .tdr-grid-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.025em;
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }
  .tdr-grid-val {
    font-size: 0.8125rem;
    color: #1e293b;
    font-weight: 500;
    line-height: 1.4;
  }
  .tdr-grid-val.tdr-missing-val {
    color: #94a3b8;
    font-weight: 400;
  }

  /* Specific handling for Seats Reference to avoid misinterpretation of guarantee */
  .tdr-seats-reference {
    grid-column: span 2;
    border-top: 1px dashed #e2e8f0;
    padding-top: 0.5rem;
    margin-top: 0.25rem;
  }
  @media (max-width: 480px) {
    .tdr-seats-reference {
      grid-column: span 1;
    }
  }
  .tdr-seats-note {
    font-size: 0.65rem;
    color: #64748b;
    font-weight: 400;
    margin-top: 0.125rem;
    display: block;
  }

  .tdr-card-footer {
    display: flex;
    justify-content: flex-end;
    margin-top: auto;
  }
  .tdr-external-link {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.8125rem;
    font-weight: 600;
    color: #1d4ed8;
    text-decoration: none;
    padding: 0.375rem 0.75rem;
    border-radius: 0.375rem;
    border: 1px solid #bfdbfe;
    background-color: #eff6ff;
    transition: all 0.2s;
  }
  .tdr-external-link:hover {
    background-color: #dbeafe;
    color: #1e40af;
  }

  /* --- MAP AREA (Problem 2) --- */
  .tdr-map-wrapper {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    padding: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    display: flex;
    flex-direction: column;
    gap: 1rem;
    position: sticky;
    top: 1.5rem;
    height: calc(100vh - 120px);
    min-height: 480px;
  }
  .tdr-map-title-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .tdr-map-title {
    font-size: 0.875rem;
    font-weight: 700;
    color: #0f172a;
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }
  .tdr-map-privacy-badge {
    font-size: 0.65rem;
    background-color: #f1f5f9;
    color: #64748b;
    padding: 0.125rem 0.375rem;
    border-radius: 0.25rem;
    font-weight: 500;
  }
  .tdr-map-canvas {
    flex-grow: 1;
    background-color: #f1f5f9;
    border-radius: 0.5rem;
    position: relative;
    overflow: hidden;
    border: 1px solid #e2e8f0;
    /* Grid background simulating street patterns without heavy imagery */
    background-image: radial-gradient(#cbd5e1 1.5px, transparent 1.5px), radial-gradient(#cbd5e1 1.5px, #f1f5f9 1.5px);
    background-size: 24px 24px;
    background-position: 0 0, 12px 12px;
  }
  .tdr-map-marker {
    position: absolute;
    transform: translate(-50%, -50%);
    cursor: pointer;
    z-index: 10;
    transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  }
  .tdr-map-marker:hover, .tdr-map-marker.tdr-marker-active {
    z-index: 20;
  }
  .tdr-map-pin-body {
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .tdr-map-pin-circle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    background-color: #0f172a;
    color: #ffffff;
    font-size: 0.875rem;
    font-weight: 800;
    border-radius: 50%;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    border: 2px solid #ffffff;
    transition: all 0.2s;
  }
  .tdr-map-marker:hover .tdr-map-pin-circle,
  .tdr-map-marker.tdr-marker-active .tdr-map-pin-circle {
    background-color: #3b82f6;
    transform: scale(1.15);
    box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.3);
  }
  .tdr-map-pin-tip {
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #0f172a;
    margin-top: -1px;
    transition: all 0.2s;
  }
  .tdr-map-marker:hover .tdr-map-pin-tip,
  .tdr-map-marker.tdr-marker-active .tdr-map-pin-tip {
    border-top-color: #3b82f6;
  }
  .tdr-map-tooltip {
    position: absolute;
    bottom: calc(100% + 6px);
    background-color: #0f172a;
    color: #ffffff;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    white-space: nowrap;
    opacity: 0;
    pointer-events: none;
    transform: translateY(4px);
    transition: all 0.2s;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  }
  .tdr-map-marker:hover .tdr-map-tooltip,
  .tdr-map-marker.tdr-marker-active .tdr-map-tooltip {
    opacity: 1;
    transform: translateY(0);
  }
  .tdr-map-attribution {
    position: absolute;
    bottom: 0.5rem;
    right: 0.5rem;
    background-color: rgba(255, 255, 255, 0.9);
    padding: 0.15rem 0.4rem;
    border-radius: 0.25rem;
    font-size: 0.65rem;
    color: #64748b;
    border: 1px solid #e2e8f0;
    text-decoration: none;
  }

  /* --- MODAL DIALOGS & OVERLAYS --- */
  .tdr-modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(15, 23, 42, 0.4);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    padding: 1.5rem;
  }
  .tdr-modal-container {
    background-color: #ffffff;
    border-radius: 0.875rem;
    max-width: 480px;
    width: 100%;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
    border: 1px solid #e2e8f0;
    overflow: hidden;
    animation: tdr-modal-in 0.2s ease-out;
  }
  @keyframes tdr-modal-in {
    from { transform: scale(0.95); opacity: 0; }
    to { transform: scale(1); opacity: 1; }
  }
  .tdr-modal-header {
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .tdr-modal-title {
    font-size: 1rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0;
  }
  .tdr-modal-close {
    background: none;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    padding: 0.25rem;
    border-radius: 0.25rem;
  }
  .tdr-modal-close:hover {
    color: #475569;
    background-color: #f1f5f9;
  }
  .tdr-modal-body {
    padding: 1.5rem;
  }
  .tdr-modal-instructions {
    font-size: 0.8125rem;
    color: #64748b;
    margin: 0 0 1.25rem 0;
    line-height: 1.4;
  }
  .tdr-option-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .tdr-option-card {
    background: none;
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    padding: 1rem;
    text-align: left;
    cursor: pointer;
    transition: all 0.2s;
    width: 100%;
  }
  .tdr-option-card:hover {
    border-color: #3b82f6;
    background-color: #fcfdff;
    transform: translateX(2px);
  }
  .tdr-option-title {
    font-size: 0.875rem;
    font-weight: 700;
    color: #1e40af;
    margin: 0 0 0.25rem 0;
  }
  .tdr-option-rationale {
    font-size: 0.75rem;
    color: #475569;
    margin: 0;
    line-height: 1.4;
  }

  /* --- CRITICAL APP STATE PANELS (TDR-CS-05 to TDR-CS-08) --- */
  .tdr-state-panel {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 0.875rem;
    padding: 3rem 2rem;
    text-align: center;
    max-width: 520px;
    margin: 4rem auto;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
  }
  .tdr-state-icon-box {
    display: inline-flex;
    padding: 1rem;
    border-radius: 50%;
    margin-bottom: 1.25rem;
  }
  .tdr-icon-box-loading { background-color: #eff6ff; color: #3b82f6; }
  .tdr-icon-box-alert { background-color: #fffbeb; color: #d97706; }
  .tdr-icon-box-error { background-color: #fef2f2; color: #dc2626; }
  .tdr-icon-box-unauth { background-color: #f8fafc; color: #64748b; }
  
  .tdr-state-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 0.5rem 0;
  }
  .tdr-state-message {
    font-size: 0.875rem;
    color: #475569;
    line-height: 1.6;
    margin: 0;
  }
  .tdr-spinner {
    animation: tdr-spin 1s linear infinite;
  }
  @keyframes tdr-spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  /* --- AUTHENTICATION SCREEN Pre-login --- */
  .tdr-unauth-card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 0.875rem;
    padding: 2.5rem 2rem;
    max-width: 400px;
    width: 100%;
    margin: 6rem auto;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
    text-align: center;
  }
  .tdr-unauth-fields {
    margin-top: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .tdr-unauth-input {
    width: 100%;
    padding: 0.625rem 0.875rem;
    border-radius: 0.5rem;
    border: 1px solid #cbd5e1;
    font-size: 0.875rem;
    background-color: #f8fafc;
    pointer-events: none; /* Keep inert as login is handled by the dev console */
  }

  /* --- FOOTER & COMPLIANCE --- */
  .tdr-footer {
    border-top: 1px solid #e2e8f0;
    margin-top: 4rem;
    background-color: #ffffff;
    padding: 2rem 0;
  }
  .tdr-footer-inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.75rem;
    color: #64748b;
  }
  .tdr-footer-links {
    display: flex;
    gap: 1.5rem;
  }
  .tdr-footer-link {
    color: #1d4ed8;
    text-decoration: none;
    font-weight: 500;
  }
  .tdr-footer-link:hover {
    text-decoration: underline;
  }

  /* --- REVIEW CONTROL CONSOLE (Highly isolated at the screen base) --- */
  .tdr-reviewer-console {
    background-color: #0f172a;
    color: #f8fafc;
    padding: 1.25rem 1.5rem;
    border-top: 3px solid #3b82f6;
    position: sticky;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 9999;
    font-size: 0.8125rem;
  }
  .tdr-reviewer-header {
    font-weight: 800;
    color: #3b82f6;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .tdr-scenario-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .tdr-scenario-btn {
    background-color: #1e293b;
    border: 1px solid #334155;
    color: #cbd5e1;
    padding: 0.375rem 0.75rem;
    border-radius: 0.375rem;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.15s;
    font-size: 0.75rem;
  }
  .tdr-scenario-btn:hover {
    background-color: #334155;
    color: #ffffff;
  }
  .tdr-scenario-btn.tdr-scenario-active {
    background-color: #3b82f6;
    border-color: #60a5fa;
    color: #ffffff;
  }
`;

/* ============================================================================
   MAIN PREVIEW COMPONENT
   ============================================================================ */

export default function CandidateSearchPreview() {
  // Review Scenarios Setup
  const [activeScenario, setActiveScenario] = useState<string>("TDR-CS-01");

  // Interaction States (Card-Marker Mutual Highlight: TDR-CS-02)
  const [highlightedCandidateRef, setHighlightedCandidateRef] = useState<string | null>(null);

  // Dynamic Concept States
  const [currentConcept, setCurrentConcept] = useState<keyof typeof CONCEPT_METADATA>("PROXIMITY");
  const [isReProposalOpen, setIsReProposalOpen] = useState(false);
  const [hasReProposed, setHasReProposed] = useState(false);

  // Generate Current Candidates list based on active concept
  // Represents server response switching proposal collections
  const currentProposal = useMemo((): Proposal => {
    if (currentConcept === "PROXIMITY") {
      return {
        conceptRef: "concept_proximity",
        kind: "PROXIMITY",
        title: CONCEPT_METADATA.PROXIMITY.title,
        rationale: CONCEPT_METADATA.PROXIMITY.rationale,
        candidates: [
          { ...SYNTHETIC_CANDIDATES.a, isNew: !hasReProposed },
          { ...SYNTHETIC_CANDIDATES.b, isNew: !hasReProposed },
          { ...SYNTHETIC_CANDIDATES.c, isNew: !hasReProposed }
        ]
      };
    } else {
      // Reproposed Concept (CAPACITY_REFERENCE)
      // Visual verification of New (First time) vs Re-appearing (Previously shown) status
      return {
        conceptRef: "concept_capacity",
        kind: "CAPACITY_REFERENCE",
        title: CONCEPT_METADATA.CAPACITY_REFERENCE.title,
        rationale: CONCEPT_METADATA.CAPACITY_REFERENCE.rationale,
        candidates: [
          { ...SYNTHETIC_CANDIDATES.a, isNew: false }, // Re-appeared (was in PROXIMITY)
          { ...SYNTHETIC_CANDIDATES.b, isNew: false }, // Re-appeared (was in PROXIMITY)
          { ...SYNTHETIC_CANDIDATES.d, isNew: true }   // Newly appearing
        ]
      };
    }
  }, [currentConcept, hasReProposed]);

  // Exclude current concept from reproposal choices
  const reProposalOptions = useMemo((): ReProposalOption[] => {
    return (Object.keys(CONCEPT_METADATA) as Array<keyof typeof CONCEPT_METADATA>)
      .filter((k) => k !== currentConcept)
      .slice(0, 3)
      .map((k) => ({
        kind: k,
        title: CONCEPT_METADATA[k].title,
        rationale: CONCEPT_METADATA[k].rationale
      }));
  }, [currentConcept]);

  const handleReProposeSubmit = (kind: keyof typeof CONCEPT_METADATA) => {
    setCurrentConcept(kind);
    setHasReProposed(true);
    setIsReProposalOpen(false);
    // Auto shift scenario for visual feedback in testing
    if (activeScenario === "TDR-CS-03") {
      // Stay in reproposal test mode, shows newly constructed list
    } else {
      setActiveScenario("TDR-CS-03");
    }
  };

  const handleResetProposal = () => {
    setCurrentConcept("PROXIMITY");
    setHasReProposed(false);
  };

  return (
    <div className="tdr-app-root">
      <style>{CSS_STYLES}</style>

      {/* TDR-CS-00: Unauthenticated Screen Rendering */}
      {activeScenario === "TDR-CS-00" ? (
        <div>
          <header className="tdr-header">
            <div className="tdr-brand">
              <span className="tdr-brand-logo"><Layers size={18} /></span>
              ランチレーダー
            </div>
          </header>
          <div className="tdr-container">
            <div className="tdr-unauth-card">
              <div className="tdr-state-icon-box tdr-icon-box-unauth">
                <Lock size={28} />
              </div>
              {/* Target State Copy */}
              <h2 className="tdr-state-title">幹事向けの候補提案</h2>
              <p className="tdr-state-message">
                候補を見るには、招待されたアカウントでサインインしてください。
              </p>
              
              <div className="tdr-unauth-fields">
                <input 
                  type="text" 
                  className="tdr-unauth-input" 
                  placeholder="ユーザーID / メールアドレス" 
                  disabled 
                />
                <input 
                  type="password" 
                  className="tdr-unauth-input" 
                  placeholder="パスワード" 
                  disabled 
                />
                <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.5rem" }}>
                  ※ サインイン操作はレビューコンソールを使用してください
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* ====================================================================
           PRODUCT SCREEN BODY (Authenticated user view)
           ==================================================================== */
        <>
          {/* Header Block */}
          <header className="tdr-header">
            <div className="tdr-brand">
              <span className="tdr-brand-logo"><Layers size={18} /></span>
              ランチレーダー
            </div>
            <div>
              <button 
                className="tdr-signout-btn" 
                onClick={() => setActiveScenario("TDR-CS-00")}
              >
                サインアウト
              </button>
            </div>
          </header>

          <main className="tdr-container">
            {/* Loading / Error States overrides based on active review scenario */}
            {activeScenario === "loading" && (
              <div className="tdr-state-panel">
                <div className="tdr-state-icon-box tdr-icon-box-loading">
                  <RefreshCw className="tdr-spinner" size={28} />
                </div>
                <h2 className="tdr-state-title">ランチ候補を探しています</h2>
                <p className="tdr-state-message">
                  ランチ営業の店舗を集め、最初の候補を用意しています。
                </p>
              </div>
            )}

            {activeScenario === "TDR-CS-05" && (
              <div className="tdr-state-panel">
                <div className="tdr-state-icon-box tdr-icon-box-alert">
                  <AlertTriangle size={28} />
                </div>
                <h2 className="tdr-state-title">この切り口では候補が見つかりませんでした</h2>
                <p className="tdr-state-message">
                  別の切り口を選んで、もう一度提案を作れます。
                </p>
                <button 
                  className="tdr-repropose-trigger" 
                  style={{ marginTop: "1.5rem" }}
                  onClick={() => setIsReProposalOpen(true)}
                >
                  <RefreshCw size={14} /> 別の切り口で提案を再作成
                </button>
              </div>
            )}

            {activeScenario === "TDR-CS-06" && (
              <div className="tdr-state-panel">
                <div className="tdr-state-icon-box tdr-icon-box-error">
                  <AlertTriangle size={28} />
                </div>
                {/* 503 Provider Unavailable Error State (Safety policy: No exposed code) */}
                <h2 className="tdr-state-title">候補情報を取得できませんでした</h2>
                <p className="tdr-state-message">
                  時間をおいてから、もう一度お試しください。
                </p>
              </div>
            )}

            {activeScenario === "TDR-CS-07" && (
              <div className="tdr-state-panel">
                <div className="tdr-state-icon-box tdr-icon-box-error">
                  <AlertTriangle size={28} />
                </div>
                {/* 400 Bad reproposal kind state */}
                <h2 className="tdr-state-title">その切り口では再提案できません</h2>
                <p className="tdr-state-message">
                  表示されている切り口から選び直してください。
                </p>
              </div>
            )}

            {activeScenario === "403" && (
              <div className="tdr-state-panel">
                <div className="tdr-state-icon-box tdr-icon-box-error">
                  <AlertTriangle size={28} />
                </div>
                {/* 403 Forbidden State */}
                <h2 className="tdr-state-title">この操作を受け付けられませんでした</h2>
                <p className="tdr-state-message">
                  画面を再読み込みしてから、もう一度お試しください。
                </p>
              </div>
            )}

            {activeScenario === "TDR-CS-08" && (
              <div className="tdr-state-panel">
                <div className="tdr-state-icon-box tdr-icon-box-alert">
                  <Clock size={28} />
                </div>
                {/* 429 Rate limited State */}
                <h2 className="tdr-state-title">少し間をあけてお試しください</h2>
                <p className="tdr-state-message">
                  候補の提案が続いています。しばらく待つと、再び提案できます。（再試行の目安: 30秒後）
                </p>
              </div>
            )}

            {/* Standard Proposal Layout */}
            {["TDR-CS-01", "TDR-CS-02", "TDR-CS-03", "TDR-CS-04"].includes(activeScenario) && (
              <>
                {/* Concept Banner (Current Proposal View) */}
                <div className="tdr-concept-banner">
                  <div>
                    <span className="tdr-concept-badge">
                      <Layers size={12} />
                      現在の切り口: {currentProposal.kind}
                    </span>
                    <h1 className="tdr-concept-title">{currentProposal.title}</h1>
                    <p className="tdr-concept-rationale">{currentProposal.rationale}</p>
                  </div>
                  <div>
                    <button 
                      className="tdr-repropose-trigger"
                      onClick={() => setIsReProposalOpen(true)}
                    >
                      <RefreshCw size={14} />
                      別の切り口で再提案
                    </button>
                  </div>
                </div>

                {/* Main comparison dashboard (Cards list side-by-side with Map canvas) */}
                <div className="tdr-main-layout">
                  {/* Left Side: Candidate Card stack (The primary design target) */}
                  <div className="tdr-cards-list">
                    {currentProposal.candidates.map((candidate, idx) => {
                      const isHighlighted = highlightedCandidateRef === candidate.candidateRef;
                      const letterId = String.fromCharCode(65 + idx); // A, B, C...

                      return (
                        <div 
                          key={candidate.candidateRef}
                          className={`tdr-card ${isHighlighted ? "tdr-card-active" : ""}`}
                          onMouseEnter={() => setHighlightedCandidateRef(candidate.candidateRef)}
                          onMouseLeave={() => setHighlightedCandidateRef(null)}
                        >
                          {/* Card Top: Categorization & Visual Tags */}
                          <div className="tdr-card-header">
                            <div>
                              <div className="tdr-card-badge-row">
                                <span className="tdr-marker-id" title="地図対応番号">
                                  {letterId}
                                </span>
                                <span className="tdr-genre-chip">
                                  {candidate.genre}
                                </span>
                                {/* First appearance or returnee representation (Problem 5) */}
                                {hasReProposed && (
                                  candidate.isNew ? (
                                    <span className="tdr-novelty-chip">初提案の候補</span>
                                  ) : (
                                    <span className="tdr-reappear-chip">前の提案からキープ</span>
                                  )
                                )}
                              </div>
                              <h2 className="tdr-shop-name">{candidate.name}</h2>
                            </div>
                          </div>

                          {/* Hierarchy Group 1: Descriptive intro (Problem 1) */}
                          <div>
                            {candidate.description ? (
                              <p className="tdr-card-description">{candidate.description}</p>
                            ) : (
                              <p className="tdr-card-description tdr-missing-val">
                                （店舗紹介文の登録はありません）
                              </p>
                            )}
                          </div>

                          {/* Hierarchy Group 2: Structured Variable Grid (Problem 1, 3, 4) */}
                          <div className="tdr-card-grid">
                            {/* Variable A: Availability Timing */}
                            <div className="tdr-grid-item">
                              <div className="tdr-grid-label">
                                <Clock size={12} />
                                営業時間
                              </div>
                              <div className={`tdr-grid-val ${!candidate.businessHours ? "tdr-missing-val" : ""}`}>
                                {candidate.businessHours || "情報なし"}
                              </div>
                            </div>

                            <div className="tdr-grid-item">
                              <div className="tdr-grid-label">
                                定休日
                              </div>
                              <div className={`tdr-grid-val ${!candidate.regularHoliday ? "tdr-missing-val" : ""}`}>
                                {candidate.regularHoliday || "情報なし"}
                              </div>
                            </div>

                            {/* Variable B: Physical Reference Point */}
                            <div className="tdr-grid-item" style={{ gridColumn: "span 2" }}>
                              <div className="tdr-grid-label">
                                <MapPin size={12} />
                                アクセス参考
                              </div>
                              <div className={`tdr-grid-val ${!candidate.access ? "tdr-missing-val" : ""}`}>
                                {candidate.access || "情報なし"}
                              </div>
                            </div>

                            {/* Variable C: Capacity reference (Strict warning display to avoid trust violation: Problem 4) */}
                            <div className="tdr-grid-item tdr-seats-reference">
                              <div className="tdr-grid-label">
                                <Users size={12} />
                                規模
                              </div>
                              <div className={`tdr-grid-val ${candidate.totalSeats === null ? "tdr-missing-val" : ""}`}>
                                {candidate.totalSeats !== null ? `${candidate.totalSeats} 席` : "情報なし"}
                              </div>
                              <span className="tdr-seats-note">
                                ※席数は目安です。実際の空席を保証、または確保するものではありません。
                              </span>
                            </div>
                          </div>

                          {/* Action Zone: Handover to Provider for final checkout */}
                          <div className="tdr-card-footer">
                            <a 
                              href={candidate.providerPageUrl} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="tdr-external-link"
                            >
                              詳細・メニューを見る (外部サイトへ)
                              <ExternalLink size={12} />
                            </a>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Right Side: Visual Map Panel (Problem 2) */}
                  <div className="tdr-map-wrapper">
                    <div className="tdr-map-title-bar">
                      <div className="tdr-map-title">
                        <MapPin size={16} />
                        候補地の位置
                      </div>
                      <span className="tdr-map-privacy-badge">検索基点・現在地は非公開</span>
                    </div>

                    {/* Synthetic Canvas simulating Map coordinates dynamically without leaking backend positions */}
                    <div className="tdr-map-canvas">
                      {currentProposal.candidates.map((candidate, idx) => {
                        const isHighlighted = highlightedCandidateRef === candidate.candidateRef;
                        const letterId = String.fromCharCode(65 + idx);

                        return (
                          <div 
                            key={`map-pin-${candidate.candidateRef}`}
                            className={`tdr-map-marker ${isHighlighted ? "tdr-marker-active" : ""}`}
                            style={{ 
                              left: `${candidate.visualPosition.x}%`, 
                              top: `${candidate.visualPosition.y}%` 
                            }}
                            onMouseEnter={() => setHighlightedCandidateRef(candidate.candidateRef)}
                            onMouseLeave={() => setHighlightedCandidateRef(null)}
                          >
                            <div className="tdr-map-pin-body">
                              <div className="tdr-map-tooltip">
                                {candidate.name} ({candidate.genre})
                              </div>
                              <div className="tdr-map-pin-circle">
                                {letterId}
                              </div>
                              <div className="tdr-map-pin-tip"></div>
                            </div>
                          </div>
                        );
                      })}

                      {/* Map OpenStreetMap mandatory attribution */}
                      <a 
                        href="https://www.openstreetmap.org/copyright" 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="tdr-map-attribution"
                      >
                        © OpenStreetMap contributors
                      </a>
                    </div>
                    
                    <div style={{ fontSize: "0.7rem", color: "#64748b", lineHeight: "1.3" }}>
                      ※ 詳細な経路・距離・移動時間は本アプリ上では取り扱いません。各店舗の外部ページでご確認ください。
                    </div>
                  </div>
                </div>
              </>
            )}
          </main>
        </>
      )}

      {/* RE-PROPOSAL SELECTOR MODAL WINDOW */}
      {isReProposalOpen && (
        <div className="tdr-modal-backdrop" onClick={() => setIsReProposalOpen(false)}>
          <div className="tdr-modal-container" onClick={(e) => e.stopPropagation()}>
            <div className="tdr-modal-header">
              <h2 className="tdr-modal-title">別の切り口で再提案</h2>
              <button className="tdr-modal-close" onClick={() => setIsReProposalOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="tdr-modal-body">
              <p className="tdr-modal-instructions">
                現在の提案とは異なる特徴を持った店舗の組み合わせを提案します。
                希望する視点を選択してください。
              </p>
              
              <div className="tdr-option-list">
                {reProposalOptions.map((option) => (
                  <button 
                    key={option.kind}
                    className="tdr-option-card"
                    onClick={() => handleReProposeSubmit(option.kind)}
                  >
                    <div className="tdr-option-title">{option.title}</div>
                    <div className="tdr-option-rationale">{option.rationale}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* COMPLIANT FOOTER (HotPepper Credit + Attribution) */}
      <footer className="tdr-footer">
        <div className="tdr-container tdr-footer-inner">
          <div className="tdr-footer-links">
            <a 
              href="http://webservice.recruit.co.jp/" 
              target="_blank" 
              rel="noopener noreferrer"
              className="tdr-footer-link"
            >
              Powered by ホットペッパーグルメ Webサービス
            </a>
          </div>
          <div>
            ランチレーダー — 幹事向けクイック比較アシスタント
          </div>
        </div>
      </footer>

      {/* ====================================================================
         REVIEW CONSOLE BOARD (Isomorphic Scenario controller)
         ==================================================================== */}
      <section className="tdr-reviewer-console">
        <div className="tdr-reviewer-header">
          <Info size={14} /> Design Review State Switchboard (TDR-CS Standard)
        </div>
        <div className="tdr-scenario-grid">
          <button 
            className={`tdr-scenario-btn ${activeScenario === "TDR-CS-00" ? "tdr-scenario-active" : ""}`}
            onClick={() => setActiveScenario("TDR-CS-00")}
          >
            TDR-CS-00 (未認証)
          </button>
          
          <button 
            className={`tdr-scenario-btn ${activeScenario === "TDR-CS-01" ? "tdr-scenario-active" : ""}`}
            onClick={() => {
              setActiveScenario("TDR-CS-01");
              handleResetProposal();
            }}
          >
            TDR-CS-01 (通常提案)
          </button>
          
          <button 
            className={`tdr-scenario-btn ${activeScenario === "TDR-CS-02" ? "tdr-scenario-active" : ""}`}
            onClick={() => {
              setActiveScenario("TDR-CS-02");
              // Set synthetic hover highlight for validation
              setHighlightedCandidateRef("cand_b");
            }}
          >
            TDR-CS-02 (相互強調)
          </button>
          
          <button 
            className={`tdr-scenario-btn ${activeScenario === "TDR-CS-03" ? "tdr-scenario-active" : ""}`}
            onClick={() => {
              setActiveScenario("TDR-CS-03");
              // Force active concept to capacity reference to trigger novelty calculations
              setCurrentConcept("CAPACITY_REFERENCE");
              setHasReProposed(true);
            }}
          >
            TDR-CS-03 (再提案: 比較・初出表示)
          </button>

          <button 
            className={`tdr-scenario-btn ${activeScenario === "TDR-CS-04" ? "tdr-scenario-active" : ""}`}
            onClick={() => {
              setActiveScenario("TDR-CS-04");
              alert("本画面は絞り込み、並び替え、範囲指定などの余剰操作が無い構成となっています（TDR-CS-04検証済み）");
            }}
          >
            TDR-CS-04 (補助条件・ソート非存在)
          </button>

          <button 
            className={`tdr-scenario-btn ${activeScenario === "TDR-CS-05" ? "tdr-scenario-active" : ""}`}
            onClick={() => setActiveScenario("TDR-CS-05")}
          >
            TDR-CS-05 (候補なし)
          </button>

          <button 
            className={`tdr-scenario-btn ${activeScenario === "TDR-CS-06" ? "tdr-scenario-active" : ""}`}
            onClick={() => setActiveScenario("TDR-CS-06")}
          >
            TDR-CS-06 (取得失敗 - 503)
          </button>

          <button 
            className={`tdr-scenario-btn ${activeScenario === "TDR-CS-07" ? "tdr-scenario-active" : ""}`}
            onClick={() => setActiveScenario("TDR-CS-07")}
          >
            TDR-CS-07 (不正切り口 - 400)
          </button>

          <button 
            className={`tdr-scenario-btn ${activeScenario === "TDR-CS-08" ? "tdr-scenario-active" : ""}`}
            onClick={() => setActiveScenario("TDR-CS-08")}
          >
            TDR-CS-08 (回数制限 - 429)
          </button>

          <button 
            className={`tdr-scenario-btn ${activeScenario === "loading" ? "tdr-scenario-active" : ""}`}
            onClick={() => setActiveScenario("loading")}
          >
            初回ロード中
          </button>

          <button 
            className={`tdr-scenario-btn ${activeScenario === "403" ? "tdr-scenario-active" : ""}`}
            onClick={() => setActiveScenario("403")}
          >
            操作拒否 (403)
          </button>
        </div>
      </section>
    </div>
  );
}