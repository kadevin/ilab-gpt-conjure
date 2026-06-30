import { getLegacyBridge } from "./state";
import {
  API_SETTINGS_STORAGE_KEY,
  DEFAULT_API_BASE_URL,
  DEFAULT_API_IMAGE_MODEL,
  DEFAULT_API_IMAGES_CONCURRENCY,
  DEFAULT_API_MODE,
  DEFAULT_CODEX_MODE,
} from "./state-defaults";
import { refreshHealth } from "./auth-source";
import { updateModeSpecificSettings } from "./api-mode-settings";
import { formatTranslation, translate } from "./i18n";
import { closeSystemSettingsModal, openSystemSettingsModal } from "./system-settings";

const bridge = getLegacyBridge();
const state = bridge.state;
const els = bridge.els;

function legacyMethod(name: string, ...args: any[]): any {
  const method = getLegacyBridge().methods[name];
  if (typeof method !== "function") {
    throw new Error("Legacy method " + name + " is not initialized");
  }
  return method(...args);
}

function setStatus(message: any, type?: any): void { legacyMethod("setStatus", message, type); }
function updateRequestPreview(): void { legacyMethod("updateRequestPreview"); }
function closePromptPopover(): void { legacyMethod("closePromptPopover"); }
function openConfirmPopover(...args: any[]): void { legacyMethod("openConfirmPopover", ...args); }

export function normalizeApiProvider(provider: any = {}, index: any = 0): any {
  const fallbackId = index === 0 ? "default" : `provider-${index + 1}`;
  const id = String(provider.id || fallbackId).trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || fallbackId;
  return {
    id,
    name: String(provider.name || (id === "default" ? "Default" : `Provider ${index + 1}`)).trim() || id,
    base_url: String(provider.base_url || DEFAULT_API_BASE_URL).trim() || DEFAULT_API_BASE_URL,
    api_key: String(provider.api_key || "").trim(),
    image_model: String(provider.image_model || DEFAULT_API_IMAGE_MODEL).trim() || DEFAULT_API_IMAGE_MODEL,
    api_mode: provider.api_mode === "responses" ? "responses" : DEFAULT_API_MODE,
    images_concurrency: normalizeApiImagesConcurrency(provider.images_concurrency),
    api_key_set: Boolean(provider.api_key_set || provider.api_key),
    api_key_masked: String(provider.api_key_masked || ""),
    api_key_source_provider_id: String(provider.api_key_source_provider_id || "").trim(),
  };
}

export function normalizeApiImagesConcurrency(value: any): number {
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed)) return DEFAULT_API_IMAGES_CONCURRENCY;
  return Math.min(32, Math.max(1, parsed));
}

function normalizeCodexMode(value: any): string {
  return value === "responses" ? "responses" : DEFAULT_CODEX_MODE;
}

function providerById(providerId: any, settings: any = state.apiSettings): any {
  const normalized = normalizeApiSettings(settings);
  return normalized.providers.find((provider: any) => provider.id === providerId) || normalized.providers[0];
}

function providerMode(provider: any): string {
  return provider?.api_mode === "responses" ? "responses" : DEFAULT_API_MODE;
}

function providerHasApiKey(provider: any): boolean {
  return Boolean(provider?.api_key || provider?.api_key_set);
}

function providerKeyLabel(provider: any): string {
  if (!providerHasApiKey(provider)) return translate("apiSettings.keyNotSet");
  return provider.api_key_masked || translate("apiSettings.keySaved");
}

function providerMetaLabel(provider: any): string {
  return [
    apiModeLabel(providerMode(provider)),
    provider?.image_model || DEFAULT_API_IMAGE_MODEL,
    formatTranslation("apiSettings.concurrencyValue", {
      concurrency: String(normalizeApiImagesConcurrency(provider?.images_concurrency)),
    }),
  ].filter(Boolean).join(" · ");
}

function uniqueCopiedProviderId(provider: any): string {
  const base = String(provider?.id || provider?.name || "provider")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    || "provider";
  const existing = new Set((state.apiSettings.providers || []).map((item: any) => item.id));
  const root = `${base}-copy`;
  if (!existing.has(root)) return root;
  for (let index = 2; index < 1000; index += 1) {
    const candidate = `${root}-${index}`;
    if (!existing.has(candidate)) return candidate;
  }
  return `provider-${Date.now()}`;
}

function copiedProviderName(provider: any): string {
  const sourceName = String(provider?.name || provider?.id || translate("apiSettings.newProvider")).trim();
  const rootName = formatTranslation("apiSettings.copyProviderName", { name: sourceName });
  const existing = new Set((state.apiSettings.providers || []).map((item: any) => String(item.name || "").trim()));
  if (!existing.has(rootName)) return rootName;
  for (let index = 2; index < 1000; index += 1) {
    const candidate = `${rootName} ${index}`;
    if (!existing.has(candidate)) return candidate;
  }
  return `${rootName} ${Date.now()}`;
}

function setElementText(element: any, value: any): void {
  if (element) element.textContent = String(value ?? "");
}

function setApiProviderEditorVisible(visible: boolean): void {
  els.apiProviderEditor?.classList.toggle("hidden", !visible);
  els.apiProviderEditor?.setAttribute("aria-hidden", visible ? "false" : "true");
  els.apiProviderDetail?.classList.toggle("hidden", visible);
  els.apiSettingsActions?.classList.toggle("hidden", visible);
  els.apiSettingsActions?.setAttribute("aria-hidden", visible ? "true" : "false");
  if (els.editApiProviderButton) els.editApiProviderButton.disabled = visible;
  if (els.addApiProviderButton) els.addApiProviderButton.disabled = visible;
  if (els.copyApiProviderButton) els.copyApiProviderButton.disabled = visible;
  if (els.sortApiProvidersButton) els.sortApiProvidersButton.disabled = visible;
  if (els.deleteApiProviderButton) {
    els.deleteApiProviderButton.disabled = visible || normalizeApiSettings(state.apiSettings).providers.length <= 1;
  }
}

function apiProviderEditorActive(): boolean {
  return Boolean(state.apiProviderEditingId && state.apiProviderDraft);
}

function draftProviderFromForm(): any {
  const draft = state.apiProviderDraft || activeApiProvider();
  return normalizeApiProvider({
    ...draft,
    name: els.apiProviderName?.value || draft.name,
    base_url: els.apiBaseUrl?.value || DEFAULT_API_BASE_URL,
    api_key: els.apiKey?.value || "",
    api_mode: els.apiMode?.value || DEFAULT_API_MODE,
    image_model: els.apiImageModel?.value || DEFAULT_API_IMAGE_MODEL,
    images_concurrency: normalizeApiImagesConcurrency(els.apiImagesConcurrency?.value),
    api_key_set: Boolean(draft.api_key_set || draft.api_key || draft.api_key_source_provider_id),
    api_key_masked: draft.api_key_masked,
    api_key_source_provider_id: draft.api_key_source_provider_id,
  }, 0);
}

function writeProviderForm(provider: any): void {
  if (els.apiProviderName) els.apiProviderName.value = provider.name || "";
  if (els.apiBaseUrl) els.apiBaseUrl.value = provider.base_url || DEFAULT_API_BASE_URL;
  if (els.apiMode) {
    els.apiMode.value = providerMode(provider);
    els.apiMode.dispatchEvent(new Event("change"));
  }
  if (els.apiImageModel) els.apiImageModel.value = provider.image_model || DEFAULT_API_IMAGE_MODEL;
  if (els.apiImagesConcurrency) els.apiImagesConcurrency.value = String(normalizeApiImagesConcurrency(provider.images_concurrency));
  if (els.apiKey) {
    els.apiKey.value = provider.api_key || "";
    els.apiKey.placeholder = provider.api_key_set && !provider.api_key
      ? translate("apiSettings.savedKeyPlaceholder")
      : "sk-...";
  }
}

function renderApiProviderList(): void {
  const settings = normalizeApiSettings(state.apiSettings);
  state.apiSettings = settings;
  const sorting = Boolean(state.apiProviderSortMode && settings.providers.length > 1);
  setElementText(els.apiProviderCount, formatTranslation("apiSettings.providerCount", {
    count: String(settings.providers.length),
  }));
  if (els.sortApiProvidersButton) {
    const canSort = settings.providers.length > 1;
    els.sortApiProvidersButton.classList.toggle("hidden", !canSort);
    els.sortApiProvidersButton.classList.toggle("active", sorting);
    els.sortApiProvidersButton.disabled = apiProviderEditorActive() || !canSort;
    els.sortApiProvidersButton.textContent = translate(sorting ? "apiSettings.finishSortProviders" : "apiSettings.sortProviders");
    els.sortApiProvidersButton.setAttribute("aria-pressed", sorting ? "true" : "false");
  }
  els.addApiProviderButton?.classList.toggle("hidden", sorting);
  if (!els.apiProviderList) return;
  els.apiProviderList.classList.toggle("is-sorting", sorting);
  els.apiProviderList.setAttribute("role", sorting ? "list" : "listbox");
  if (sorting) {
    const rows = settings.providers.map((provider: any, index: number) => {
      const row = document.createElement("div");
      row.className = `api-provider-sort-row${provider.id === settings.active_provider_id ? " active" : ""}`;
      row.dataset.apiProviderId = provider.id;
      row.setAttribute("role", "listitem");
      const content = document.createElement("div");
      content.className = "api-provider-sort-content";
      const name = document.createElement("strong");
      name.textContent = provider.name || provider.id;
      const meta = document.createElement("span");
      meta.textContent = providerMetaLabel(provider);
      content.append(name, meta);
      const controls = document.createElement("div");
      controls.className = "api-provider-sort-actions";
      [
        ["up", "apiSettings.moveProviderUp", "apiSettings.moveProviderUpAria", index <= 0],
        ["down", "apiSettings.moveProviderDown", "apiSettings.moveProviderDownAria", index >= settings.providers.length - 1],
      ].forEach(([direction, labelKey, ariaKey, disabled]: any[]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "ghost-button api-provider-sort-button";
        button.dataset.apiProviderId = provider.id;
        button.dataset.apiProviderSort = direction;
        button.disabled = Boolean(disabled);
        button.textContent = translate(labelKey);
        button.setAttribute("aria-label", formatTranslation(ariaKey, { provider: provider.name || provider.id }));
        controls.append(button);
      });
      row.append(content, controls);
      return row;
    });
    els.apiProviderList.replaceChildren(...rows);
    return;
  }
  const buttons = settings.providers.map((provider: any) => {
    const button = document.createElement("button");
    const active = provider.id === settings.active_provider_id;
    button.type = "button";
    button.className = `api-provider-choice${active ? " active" : ""}`;
    button.dataset.apiProviderId = provider.id;
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", active ? "true" : "false");
    const name = document.createElement("strong");
    name.textContent = provider.name || provider.id;
    const meta = document.createElement("span");
    meta.textContent = providerMetaLabel(provider);
    button.append(name, meta);
    return button;
  });
  els.apiProviderList.replaceChildren(...buttons);
}

function renderApiProviderDetail(): void {
  const provider = activeApiProvider();
  setElementText(els.apiProviderDetailBaseUrl, provider.base_url || DEFAULT_API_BASE_URL);
  setElementText(els.apiProviderDetailKey, providerKeyLabel(provider));
  setElementText(els.apiProviderDetailMode, apiModeLabel(providerMode(provider)));
  setElementText(els.apiProviderDetailConcurrency, normalizeApiImagesConcurrency(provider.images_concurrency));
}

function renderApiProviderEditor(): void {
  const editing = apiProviderEditorActive();
  setApiProviderEditorVisible(editing);
  if (!editing) return;
  const isNew = Boolean(state.apiProviderDraftIsNew);
  setElementText(els.apiProviderEditorTitle, translate(isNew ? "apiSettings.newProviderTitle" : "apiSettings.editProvider"));
  writeProviderForm(state.apiProviderDraft);
}

function applyApiProviderDraft(settings: any): any {
  if (!apiProviderEditorActive()) return normalizeApiSettings(settings);
  const draft = draftProviderFromForm();
  const normalized = normalizeApiSettings(settings);
  const index = normalized.providers.findIndex((provider: any) => provider.id === draft.id);
  if (index >= 0) {
    normalized.providers[index] = normalizeApiProvider({ ...normalized.providers[index], ...draft }, index);
  } else {
    normalized.providers.push(normalizeApiProvider(draft, normalized.providers.length));
  }
  normalized.active_provider_id = draft.id;
  state.apiProviderEditingId = null;
  state.apiProviderDraft = null;
  state.apiProviderDraftIsNew = false;
  return normalizeApiSettings(normalized);
}

export function normalizeApiSettings(settings: any = {}): any {
  const rawProviders = Array.isArray(settings.providers) && settings.providers.length
    ? settings.providers
    : [{
      id: settings.active_provider_id || "default",
      name: settings.name || "Default",
      base_url: settings.base_url,
      api_key: settings.api_key,
      image_model: settings.image_model,
      api_mode: settings.api_mode,
      images_concurrency: settings.images_concurrency,
      api_key_set: settings.api_key_set,
      api_key_masked: settings.api_key_masked,
    }];
  const providers: any[] = [];
  const seen = new Set<string>();
  rawProviders.forEach((provider: any, index: number) => {
    const normalized = normalizeApiProvider(provider, index);
    if (seen.has(normalized.id)) return;
    seen.add(normalized.id);
    providers.push(normalized);
  });
  if (!providers.length) providers.push(normalizeApiProvider({}, 0));
  const requestedActive = String(settings.active_provider_id || providers[0].id).trim().toLowerCase();
  const activeProvider = providers.find((provider) => provider.id === requestedActive) || providers[0];
  return {
    codex_mode: normalizeCodexMode(settings.codex_mode),
    active_provider_id: activeProvider.id,
    providers,
  };
}

export function activeApiProvider(): any {
  const settings = normalizeApiSettings(state.apiSettings);
  state.apiSettings = settings;
  return settings.providers.find((provider: any) => provider.id === settings.active_provider_id) || settings.providers[0];
}

export function restoreApiSettings(): void {
  try {
    const saved = JSON.parse(localStorage.getItem(API_SETTINGS_STORAGE_KEY) || "{}");
    state.apiSettings = normalizeApiSettings(saved);
  } catch {
    state.apiSettings = normalizeApiSettings();
  }
}

export function persistApiSettings(): void {
  try {
    localStorage.setItem(API_SETTINGS_STORAGE_KEY, JSON.stringify({
      codex_mode: state.apiSettings.codex_mode,
      active_provider_id: state.apiSettings.active_provider_id,
      providers: state.apiSettings.providers,
    }));
  } catch {
    // Browser storage may be unavailable in restricted contexts.
  }
}

export function mergeApiProviderKeys(serverSettings: any): any {
  const localById = new Map<string, any>((state.apiSettings.providers || []).map((provider: any) => [provider.id, provider]));
  const normalized = normalizeApiSettings(serverSettings);
  normalized.providers = normalized.providers.map((provider: any) => {
    const local = localById.get(provider.id);
    return local?.api_key ? { ...provider, api_key: local.api_key } : provider;
  });
  return normalized;
}

export async function refreshApiSettings(): Promise<void> {
  try {
    const response = await fetch("/api/api-settings");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || translate("apiSettings.loadFailed"));
    state.apiSettings = mergeApiProviderKeys(data.settings || {});
    populateApiSettingsForm();
    renderAuthSourceAfterProviderChange();
  } catch (error: any) {
    setApiSettingsFeedback(error.message || translate("apiSettings.loadFailed"), "error");
  }
}

export function populateApiSettingsForm(): void {
  const provider = activeApiProvider();
  if (els.codexMode) {
    els.codexMode.value = currentCodexMode();
    els.codexMode.dispatchEvent(new Event("change"));
  }
  if (els.apiProviderQuick) {
    els.apiProviderQuick.innerHTML = "";
    state.apiSettings.providers.forEach((item: any) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.name || item.id;
      els.apiProviderQuick.append(option);
    });
    els.apiProviderQuick.value = provider.id;
  }
  if (els.apiProvider) {
    els.apiProvider.innerHTML = "";
    state.apiSettings.providers.forEach((item: any) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.name || item.id;
      els.apiProvider.append(option);
    });
    els.apiProvider.value = provider.id;
  }
  renderApiProviderList();
  renderApiProviderDetail();
  renderApiProviderEditor();
  updateModeSpecificSettings();
}

export function readApiSettingsForm(options: any = {}): any {
  const settings = normalizeApiSettings(state.apiSettings);
  settings.codex_mode = normalizeCodexMode(els.codexMode?.value || settings.codex_mode);
  state.apiSettings = options.applyProviderDraft ? applyApiProviderDraft(settings) : normalizeApiSettings(settings);
  return state.apiSettings;
}

export function currentApiProviderId(): string {
  return activeApiProvider().id;
}

export function currentApiProviderLabel(): string {
  const provider = activeApiProvider();
  return String(provider.name || provider.id || "").trim() || provider.id;
}

export function addApiProvider(): void {
  if (apiProviderEditorActive()) {
    setApiSettingsFeedback(translate("apiSettings.finishEditFirst"), "error");
    return;
  }
  state.apiProviderSortMode = false;
  const id = `provider-${Date.now()}`;
  state.apiProviderEditingId = id;
  state.apiProviderDraftIsNew = true;
  state.apiProviderDraft = normalizeApiProvider({
    id,
    name: translate("apiSettings.newProvider"),
    base_url: DEFAULT_API_BASE_URL,
    image_model: DEFAULT_API_IMAGE_MODEL,
    api_mode: DEFAULT_API_MODE,
    images_concurrency: DEFAULT_API_IMAGES_CONCURRENCY,
  }, state.apiSettings.providers.length);
  populateApiSettingsForm();
  setApiSettingsFeedback(translate("apiSettings.newDraftStatus"), "running");
  els.apiProviderName?.focus();
}

export function copyApiProvider(): void {
  if (apiProviderEditorActive()) {
    setApiSettingsFeedback(translate("apiSettings.finishEditFirst"), "error");
    return;
  }
  state.apiProviderSortMode = false;
  const provider = activeApiProvider();
  const copiesSavedKey = providerHasApiKey(provider);
  const id = uniqueCopiedProviderId(provider);
  state.apiProviderEditingId = id;
  state.apiProviderDraftIsNew = true;
  state.apiProviderDraft = normalizeApiProvider({
    ...provider,
    id,
    name: copiedProviderName(provider),
    api_key: "",
    api_key_set: copiesSavedKey,
    api_key_masked: provider.api_key_masked || "",
    api_key_source_provider_id: copiesSavedKey ? provider.id : "",
  }, state.apiSettings.providers.length);
  populateApiSettingsForm();
  setApiSettingsFeedback(translate(copiesSavedKey ? "apiSettings.copyProviderStatus" : "apiSettings.copyProviderWithoutKeyStatus"), "running");
  els.apiProviderName?.focus();
}

export function deleteApiProvider(): void {
  if (apiProviderEditorActive()) {
    setApiSettingsFeedback(translate("apiSettings.finishEditFirst"), "error");
    return;
  }
  if (state.apiSettings.providers.length <= 1) return;
  const activeId = state.apiSettings.active_provider_id;
  state.apiSettings.providers = state.apiSettings.providers.filter((provider: any) => provider.id !== activeId);
  state.apiSettings.active_provider_id = state.apiSettings.providers[0]?.id || "default";
  if (state.apiSettings.providers.length <= 1) state.apiProviderSortMode = false;
  populateApiSettingsForm();
  persistApiSettings();
  setApiSettingsFeedback(translate("apiSettings.deleteProviderStatus"), "running");
  renderAuthSourceAfterProviderChange();
}

export function confirmDeleteApiProvider(anchor: any = els.deleteApiProviderButton): void {
  if (apiProviderEditorActive()) {
    setApiSettingsFeedback(translate("apiSettings.finishEditFirst"), "error");
    return;
  }
  if (state.apiSettings.providers.length <= 1) return;
  const provider = activeApiProvider();
  openConfirmPopover(anchor || els.deleteApiProviderButton, {
    title: translate("apiSettings.deleteProviderTitle"),
    message: formatTranslation("apiSettings.deleteProviderMessage", {
      provider: provider.name || provider.id,
    }),
    detail: translate("apiSettings.deleteProviderDetail"),
    confirmText: translate("action.delete"),
    onConfirm: () => deleteApiProvider(),
  });
}

export function openApiSettingsModal(): void {
  closePromptPopover();
  state.apiProviderEditingId = null;
  state.apiProviderDraft = null;
  state.apiProviderDraftIsNew = false;
  populateApiSettingsForm();
  setApiSettingsFeedback("", "");
  openSystemSettingsModal("api");
}

export function closeApiSettingsModal(): void {
  closeSystemSettingsModal();
}

export function selectApiProvider(providerId: any): void {
  const id = String(providerId || "").trim();
  if (!id) return;
  if (apiProviderEditorActive()) {
    setApiSettingsFeedback(translate("apiSettings.finishEditFirst"), "error");
    return;
  }
  if (state.apiProviderSortMode) return;
  const provider = providerById(id);
  state.apiSettings = normalizeApiSettings({
    ...state.apiSettings,
    active_provider_id: provider.id,
  });
  populateApiSettingsForm();
  persistApiSettings();
  renderAuthSourceAfterProviderChange();
}

export function editApiProvider(): void {
  if (apiProviderEditorActive()) return;
  state.apiProviderSortMode = false;
  const provider = activeApiProvider();
  state.apiProviderEditingId = provider.id;
  state.apiProviderDraftIsNew = false;
  state.apiProviderDraft = normalizeApiProvider({ ...provider }, 0);
  populateApiSettingsForm();
  setApiSettingsFeedback(translate("apiSettings.editDraftStatus"), "running");
  els.apiProviderName?.focus();
}

export function cancelApiProviderEdit(): void {
  if (!apiProviderEditorActive()) return;
  state.apiProviderEditingId = null;
  state.apiProviderDraft = null;
  state.apiProviderDraftIsNew = false;
  populateApiSettingsForm();
  setApiSettingsFeedback("", "");
}

export function toggleApiProviderSortMode(): void {
  if (apiProviderEditorActive()) {
    setApiSettingsFeedback(translate("apiSettings.finishEditFirst"), "error");
    return;
  }
  const settings = normalizeApiSettings(state.apiSettings);
  if (settings.providers.length <= 1) return;
  state.apiProviderSortMode = !state.apiProviderSortMode;
  renderApiProviderList();
  setApiSettingsFeedback(state.apiProviderSortMode ? translate("apiSettings.sortProviderModeStatus") : "", state.apiProviderSortMode ? "running" : "");
}

export function moveApiProvider(providerId: any, direction: any): void {
  if (!state.apiProviderSortMode || apiProviderEditorActive()) return;
  const settings = normalizeApiSettings(state.apiSettings);
  const index = settings.providers.findIndex((provider: any) => provider.id === providerId);
  const offset = direction === "up" ? -1 : direction === "down" ? 1 : 0;
  const nextIndex = index + offset;
  if (index < 0 || nextIndex < 0 || nextIndex >= settings.providers.length) return;
  const providers = [...settings.providers];
  [providers[index], providers[nextIndex]] = [providers[nextIndex], providers[index]];
  state.apiSettings = normalizeApiSettings({
    ...settings,
    providers,
    active_provider_id: settings.active_provider_id,
  });
  persistApiSettings();
  renderApiProviderList();
  setApiSettingsFeedback(translate("apiSettings.sortProviderStatus"), "running");
}

export async function saveApiProviderEdit(): Promise<void> {
  if (!apiProviderEditorActive()) return;
  await saveApiSettings();
}

function renderAuthSourceAfterProviderChange(): void {
  legacyMethod("renderAuthSource", state.authStatus);
  updateModeSpecificSettings();
  updateRequestPreview();
}

export function currentApiImageModel(): string {
  return (activeApiProvider().image_model || DEFAULT_API_IMAGE_MODEL).trim() || DEFAULT_API_IMAGE_MODEL;
}

export function currentApiMode(): string {
  return activeApiProvider().api_mode === "responses" ? "responses" : DEFAULT_API_MODE;
}

export function currentCodexMode(): string {
  state.apiSettings = normalizeApiSettings(state.apiSettings);
  return normalizeCodexMode(state.apiSettings.codex_mode);
}

export function currentApiImagesConcurrency(): number {
  return normalizeApiImagesConcurrency(activeApiProvider().images_concurrency);
}

export function apiModeLabel(mode: any): string {
  return mode === "responses" ? "Responses" : translate("apiSettings.modeImagesShort");
}

export function codexModeLabel(mode: any): string {
  return mode === "responses" ? "Responses" : "Image";
}

export function backendForAuthSource(authSource: any, apiMode: any = currentApiMode(), codexMode: any = currentCodexMode()): string {
  if (authSource === "api") {
    return apiMode === "responses" ? "openai_responses" : "openai_images";
  }
  return codexMode === "responses" ? "codex_responses" : "codex_images";
}

export function taskBackendValue(task: any): string {
  return String(task?.backend || task?.requested_backend || "").trim();
}

export function taskApiProviderId(task: any): string {
  return String(
    task?.api_provider_id
    || task?.params?.api_provider_id
    || task?.request?.webui_api_provider_id
    || task?.request?.api_provider_id
    || "",
  ).trim();
}

export function taskApiProviderLabel(task: any): string {
  const providerId = taskApiProviderId(task);
  if (!providerId) return "";
  const providerName = String(
    task?.api_provider_name
    || task?.params?.api_provider_name
    || task?.request?.webui_api_provider_name
    || task?.request?.api_provider_name
    || "",
  ).trim();
  const configuredProvider = state.apiSettings.providers.find((provider: any) => provider.id === providerId);
  const label = providerName || configuredProvider?.name || providerId;
  return label === providerId ? label : `${label} (${providerId})`;
}

export function taskBackendLabel(task: any): string {
  const backend = taskBackendValue(task);
  const provider = taskApiProviderLabel(task);
  return [backend, provider].filter(Boolean).join(" · ");
}

export function setApiSettingsFeedback(message: any, type: any = ""): void {
  [els.apiSettingsStatus, els.codexSettingsStatus].filter(Boolean).forEach((statusElement: any) => {
    statusElement.textContent = message;
    statusElement.className = `api-settings-feedback settings-action-status ${type || ""}`.trim();
  });
}

function saveButtons(): any[] {
  return [els.saveApiSettingsButton, els.saveCodexSettingsButton, els.saveApiProviderEditButton].filter(Boolean);
}

function setSaveButtonsDisabled(disabled: boolean): void {
  saveButtons().forEach((button) => { button.disabled = disabled; });
}

function setSaveButtonText(stateName: "saving" | "saved" | "failed" | "default"): void {
  const apiText = {
    saving: translate("apiSettings.saving"),
    saved: translate("apiSettings.savedShort"),
    failed: translate("apiSettings.saveFailedShort"),
    default: translate("apiSettings.saveSelection"),
  }[stateName];
  const providerText = {
    saving: translate("apiSettings.saving"),
    saved: translate("apiSettings.savedShort"),
    failed: translate("apiSettings.saveFailedShort"),
    default: translate("apiSettings.saveProvider"),
  }[stateName];
  const codexText = {
    saving: translate("apiSettings.saving"),
    saved: translate("apiSettings.savedShort"),
    failed: translate("apiSettings.saveFailedShort"),
    default: translate("codexSettings.save"),
  }[stateName];
  if (els.saveApiSettingsButton) els.saveApiSettingsButton.textContent = apiText;
  if (els.saveApiProviderEditButton) els.saveApiProviderEditButton.textContent = providerText;
  if (els.saveCodexSettingsButton) els.saveCodexSettingsButton.textContent = codexText;
}

export async function saveApiSettings(): Promise<void> {
  if (!saveButtons().length) return;
  if (state.apiSettingsSaveTimerId) {
    window.clearTimeout(state.apiSettingsSaveTimerId);
    state.apiSettingsSaveTimerId = null;
  }
  const settings = readApiSettingsForm({ applyProviderDraft: true });
  persistApiSettings();
  const payload: any = {
    codex_mode: settings.codex_mode,
    active_provider_id: settings.active_provider_id,
    providers: settings.providers.map((provider: any) => {
      const item: any = {
        id: provider.id,
        name: provider.name,
        base_url: provider.base_url,
        image_model: provider.image_model,
        api_mode: provider.api_mode,
      };
      item.images_concurrency = provider.images_concurrency;
      if (provider.api_key || !provider.api_key_set) item.api_key = provider.api_key;
      if (!provider.api_key && provider.api_key_source_provider_id) {
        item.api_key_source_provider_id = provider.api_key_source_provider_id;
      }
      return item;
    }),
  };
  setSaveButtonsDisabled(true);
  setSaveButtonText("saving");
  setApiSettingsFeedback(translate("apiSettings.savingStatus"), "running");
  try {
    const response = await fetch("/api/api-settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || translate("apiSettings.saveFailed"));
    state.apiSettings = mergeApiProviderKeys(data.settings || {});
    state.apiProviderEditingId = null;
    state.apiProviderDraft = null;
    state.apiProviderDraftIsNew = false;
    persistApiSettings();
    populateApiSettingsForm();
    setApiSettingsFeedback(formatTranslation("apiSettings.savedSummary", {
      codex: codexModeLabel(currentCodexMode()),
      provider: activeApiProvider().name,
      mode: apiModeLabel(currentApiMode()),
      model: currentApiImageModel(),
      concurrency: currentApiImagesConcurrency(),
    }), "ok");
    setSaveButtonText("saved");
    state.apiSettingsSaveTimerId = window.setTimeout(() => {
      setSaveButtonText("default");
      state.apiSettingsSaveTimerId = null;
    }, 1600);
    setStatus(translate("apiSettings.savedStatus"), "ok");
    await refreshHealth();
    updateRequestPreview();
  } catch (error: any) {
    setApiSettingsFeedback(error.message || translate("apiSettings.saveFailed"), "error");
    setSaveButtonText("failed");
    setStatus(error.message || translate("apiSettings.saveFailed"), "error");
  } finally {
    setSaveButtonsDisabled(false);
    if (!state.apiSettingsSaveTimerId && (
      els.saveApiSettingsButton?.textContent !== translate("apiSettings.saveSelection")
      || els.saveApiProviderEditButton?.textContent !== translate("apiSettings.saveProvider")
      || els.saveCodexSettingsButton?.textContent !== translate("codexSettings.save")
    )) {
      state.apiSettingsSaveTimerId = window.setTimeout(() => {
        setSaveButtonText("default");
        state.apiSettingsSaveTimerId = null;
      }, 1600);
    }
  }
}
