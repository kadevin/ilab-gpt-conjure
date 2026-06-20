from __future__ import annotations

from pathlib import Path
import unittest


class PortablePackagingTests(unittest.TestCase):
    def test_github_workflows_use_node24_compatible_actions(self) -> None:
        workflow_paths = [
            Path(".github/workflows/ci.yml"),
            Path(".github/workflows/release-portable.yml"),
        ]
        deprecated_actions = [
            "actions/checkout@v4",
            "actions/setup-node@v4",
            "actions/setup-python@v5",
            "actions/upload-artifact@v4",
            "actions/download-artifact@v4",
        ]

        combined = "\n".join(path.read_text(encoding="utf-8") for path in workflow_paths)
        for deprecated_action in deprecated_actions:
            self.assertNotIn(deprecated_action, combined)

        self.assertIn("actions/checkout@v7", combined)
        self.assertIn("actions/setup-node@v6", combined)
        self.assertIn("actions/setup-python@v6", combined)
        self.assertIn("actions/upload-artifact@v6", combined)
        self.assertIn("actions/download-artifact@v8", combined)

    def test_ci_workflow_avoids_github_unsupported_job_hashfiles_if(self) -> None:
        workflow = Path(".github/workflows/ci.yml")
        self.assertTrue(workflow.exists(), f"{workflow} should exist")

        text = workflow.read_text(encoding="utf-8")
        self.assertIn("name: CI", text)
        self.assertIn("Public export guard", text)
        self.assertIn("github.repository == 'kadevin/ilab-gpt-conjure'", text)
        self.assertNotIn("hashFiles('.public-export-manifest.json')", text)

    def test_windows_portable_packaging_files_define_self_contained_bundle(self) -> None:
        build_script = Path("packaging/windows/build-portable.ps1")
        launcher = Path("packaging/windows/Start WebUI Portable.bat")
        updater = Path("packaging/windows/Update WebUI Portable.bat")
        updater_helper = Path("packaging/windows/Update WebUI Portable.ps1")
        readme = Path("packaging/windows/README-portable.md")
        notices = Path("packaging/windows/THIRD_PARTY_NOTICES.md")

        for path in (build_script, launcher, updater, updater_helper, readme, notices):
            self.assertTrue(path.exists(), f"{path} should exist")

        build_text = build_script.read_text(encoding="utf-8")
        self.assertIn('$PythonVersion = "3.11.9"', build_text)
        self.assertIn("python-${PythonVersion}-embed-amd64.zip", build_text)
        self.assertIn("get-pip.py", build_text)
        self.assertIn("requirements-webui.txt", build_text)
        self.assertIn("certifi\\cacert.pem", build_text)
        self.assertIn("Start WebUI Portable.bat", build_text)
        self.assertIn("Update WebUI Portable.bat", build_text)
        self.assertIn("Update WebUI Portable.ps1", build_text)
        self.assertIn("THIRD_PARTY_NOTICES.md", build_text)
        self.assertIn("portable-version.txt", build_text)
        self.assertIn("Invoke-WebRequest", build_text)
        self.assertIn("Compress-Archive", build_text)
        self.assertIn("codex_image", build_text)

        launcher_text = launcher.read_text(encoding="utf-8")
        self.assertIn(r"python\python.exe", launcher_text)
        self.assertIn("codex_image.webui.startup_auth", launcher_text)
        self.assertIn("webui-auth-settings.json", launcher_text)
        self.assertIn("SSL_CERT_FILE", launcher_text)
        self.assertIn("REQUESTS_CA_BUNDLE", launcher_text)
        self.assertIn(r"python\Lib\site-packages\certifi\cacert.pem", launcher_text)
        self.assertIn("portable_webui_app:app", launcher_text)
        self.assertIn("api/health", launcher_text)
        self.assertIn("data", launcher_text)
        self.assertIn("ILAB_CONJURE_BUNDLE_DIR", launcher_text)
        self.assertIn("urllib.request.urlopen", launcher_text)
        self.assertNotIn("powershell", launcher_text.lower())
        self.assertNotIn("Invoke-RestMethod", launcher_text)
        self.assertNotIn("ExecutionPolicy", launcher_text)
        self.assertNotIn("LATEST_RELEASE_URL", launcher_text)
        self.assertNotIn("update-notice.json", launcher_text)
        self.assertNotIn("ILAB_SKIP_VERSION_CHECK", launcher_text)
        self.assertNotIn("ilab-gpt-conjure-portable-launcher", launcher_text)

        updater_text = updater.read_text(encoding="utf-8")
        updater_helper_text = updater_helper.read_text(encoding="utf-8")
        self.assertIn("Update WebUI Portable.ps1", updater_text)
        self.assertIn("powershell -NoProfile -File", updater_text)
        self.assertNotIn("ExecutionPolicy Bypass", updater_text)
        self.assertIn("https://api.github.com/repos/kadevin/ilab-gpt-conjure/releases/latest", updater_helper_text)
        self.assertIn("browser_download_url", updater_helper_text)
        self.assertIn("ilab-gpt-conjure_windows_portable_x64_", updater_helper_text)
        self.assertIn("Get-FileHash", updater_helper_text)
        self.assertIn("Expand-Archive", updater_helper_text)
        self.assertIn("data", updater_helper_text)
        self.assertIn("backup", updater_helper_text.lower())
        self.assertIn("Do not move data", updater_helper_text)
        self.assertIn('$VersionFile = Join-Path $BundleDir "portable-version.txt"', updater_helper_text)
        self.assertIn('"portable-version.txt"', updater_helper_text)
        self.assertIn("Get-CurrentPortableVersion", updater_helper_text)
        self.assertIn("Test-VersionCurrentOrNewer", updater_helper_text)
        self.assertIn("Already up to date", updater_helper_text)
        self.assertIn("update-notice.json", updater_helper_text)
        self.assertIn("Clear-UpdateNotice", updater_helper_text)
        self.assertIn("Release asset:", updater_helper_text)
        self.assertIn("SHA256 file:", updater_helper_text)
        self.assertIn("Download URL:", updater_helper_text)
        self.assertIn("Assert-PathInsideBundle", updater_helper_text)
        self.assertIn("Refusing to modify path outside bundle", updater_helper_text)
        self.assertLess(
            updater_helper_text.index('Write-Step "Checking latest release"'),
            updater_helper_text.index('Write-Host "Close the WebUI server window before updating."'),
        )

        readme_text = readme.read_text(encoding="utf-8")
        self.assertIn("Do not put API keys", readme_text)
        self.assertIn("OpenAI-compatible API", readme_text)
        self.assertIn("Update WebUI Portable.bat", readme_text)
        self.assertIn("latest GitHub Release", readme_text)
        self.assertIn("does not contact GitHub", readme_text)
        self.assertIn("or update files automatically", readme_text)
        self.assertIn("selected release asset", readme_text)
        self.assertNotIn("ILAB_SKIP_VERSION_CHECK=1", readme_text)

    def test_macos_portable_packaging_files_define_arch_specific_bundles(self) -> None:
        build_script = Path("packaging/macos/build-portable.sh")
        launcher = Path("packaging/macos/Start WebUI Portable.command")
        updater = Path("packaging/macos/Update WebUI Portable.command")
        app_module = Path("packaging/macos/portable_webui_app.py")
        readme = Path("packaging/macos/README-portable.md")
        notices = Path("packaging/macos/THIRD_PARTY_NOTICES.md")

        for path in (build_script, launcher, updater, app_module, readme, notices):
            self.assertTrue(path.exists(), f"{path} should exist")

        build_text = build_script.read_text(encoding="utf-8")
        self.assertIn('PYTHON_VERSION="3.11.9"', build_text)
        self.assertIn("python-${PYTHON_VERSION}-macos11.pkg", build_text)
        self.assertIn('PACKAGE_ARCH="arm64"', build_text)
        self.assertIn('PACKAGE_ARCH="x64"', build_text)
        self.assertIn('x86_64)', build_text)
        self.assertIn('macos_portable_${PACKAGE_ARCH}', build_text)
        self.assertIn("pkgutil --expand-full", build_text)
        self.assertIn("install_name_tool", build_text)
        self.assertIn('name "*.dylib"', build_text)
        self.assertIn("codesign --force --sign -", build_text)
        self.assertIn("requirements-webui.txt", build_text)
        self.assertIn("certifi/cacert.pem", build_text)
        self.assertIn("Start WebUI Portable.command", build_text)
        self.assertIn("Update WebUI Portable.command", build_text)
        self.assertIn("THIRD_PARTY_NOTICES.md", build_text)
        self.assertIn("portable-version.txt", build_text)
        self.assertIn("ditto -c -k", build_text)
        self.assertIn("portable_webui_app", build_text)

        launcher_text = launcher.read_text(encoding="utf-8")
        self.assertIn('export PATH="/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"', launcher_text)
        self.assertIn("Python.framework/Versions/3.11/bin/python3", launcher_text)
        self.assertIn("codex_image.webui.startup_auth", launcher_text)
        self.assertIn("webui-auth-settings.json", launcher_text)
        self.assertIn("PYTHON_FRAMEWORK=", launcher_text)
        self.assertIn("clear_macos_quarantine", launcher_text)
        self.assertIn("com.apple.quarantine", launcher_text)
        self.assertIn("xattr -dr com.apple.quarantine", launcher_text)
        self.assertIn("for bundle_path in", launcher_text)
        self.assertNotIn("for path in", launcher_text)
        self.assertIn("SSL_CERT_FILE", launcher_text)
        self.assertIn("REQUESTS_CA_BUNDLE", launcher_text)
        self.assertIn(".deps/certifi/cacert.pem", launcher_text)
        self.assertIn("portable_webui_app:app", launcher_text)
        self.assertIn("api/health", launcher_text)
        self.assertIn("data", launcher_text)
        self.assertIn("ILAB_CONJURE_BUNDLE_DIR", launcher_text)
        self.assertNotIn("LATEST_RELEASE_URL", launcher_text)
        self.assertNotIn("check_latest_release_notice", launcher_text)
        self.assertNotIn("--max-time 2", launcher_text)
        self.assertNotIn("ILAB_SKIP_VERSION_CHECK", launcher_text)
        self.assertNotIn("json.dump", launcher_text)
        self.assertNotIn("ilab-gpt-conjure-portable-launcher", launcher_text)
        self.assertNotIn("update-notice.json", launcher_text)

        updater_text = updater.read_text(encoding="utf-8")
        self.assertIn("https://api.github.com/repos/kadevin/ilab-gpt-conjure/releases/latest", updater_text)
        self.assertIn("browser_download_url", updater_text)
        self.assertIn("ilab-gpt-conjure_macos_portable_${PACKAGE_ARCH}_", updater_text)
        self.assertIn("shasum -a 256", updater_text)
        self.assertIn("ditto -x -k", updater_text)
        self.assertIn("data", updater_text)
        self.assertIn("backup", updater_text.lower())
        self.assertIn("Do not move data", updater_text)
        self.assertIn('VERSION_FILE="${BUNDLE_DIR}/portable-version.txt"', updater_text)
        self.assertIn('"portable-version.txt"', updater_text)
        self.assertIn("current_portable_version", updater_text)
        self.assertIn("version_is_current_or_newer", updater_text)
        self.assertIn("Already up to date", updater_text)
        self.assertIn("update-notice.json", updater_text)
        self.assertIn("clear_update_notice", updater_text)
        self.assertIn("Release asset:", updater_text)
        self.assertIn("SHA256 file:", updater_text)
        self.assertIn("Download URL:", updater_text)
        self.assertIn("assert_in_bundle", updater_text)
        self.assertIn("Refusing to modify path outside bundle", updater_text)
        self.assertLess(
            updater_text.index('step "Checking latest release"'),
            updater_text.index('echo "Close the WebUI server window before updating."'),
        )
        self.assertIn("xattr -dr com.apple.quarantine", updater_text)

        app_module_text = app_module.read_text(encoding="utf-8")
        self.assertIn("ILAB_CONJURE_DATA_DIR", app_module_text)
        self.assertIn("create_app", app_module_text)

        readme_text = readme.read_text(encoding="utf-8")
        self.assertIn("Double-click", readme_text)
        self.assertIn("Apple Silicon", readme_text)
        self.assertIn("Intel", readme_text)
        self.assertIn("unsigned portable zip", readme_text)
        self.assertIn("tries to\nremove quarantine", readme_text)
        self.assertIn("xattr -dr com.apple.quarantine", readme_text)
        self.assertIn("OpenAI-compatible API", readme_text)
        self.assertIn("Update WebUI Portable.command", readme_text)
        self.assertIn("GitHub Releases", readme_text)
        self.assertIn("does not contact GitHub", readme_text)
        self.assertIn("or update files automatically", readme_text)
        self.assertIn("selected release asset", readme_text)
        self.assertNotIn("ILAB_SKIP_VERSION_CHECK=1", readme_text)

    def test_root_launchers_initialize_auth_settings(self) -> None:
        mac_launcher = Path("Start WebUI.command")
        debug_launcher = Path("Start WebUI Debug.command")
        windows_launcher = Path("Start WebUI.bat")

        for path in (mac_launcher, debug_launcher, windows_launcher):
            self.assertTrue(path.exists(), f"{path} should exist")
            text = path.read_text(encoding="utf-8")
            self.assertIn("codex_image.webui.startup_auth", text)
            self.assertIn("output", text)
            self.assertIn("webui-auth-settings.json", text)

    def test_portable_release_workflow_runs_after_ci_success(self) -> None:
        workflow = Path(".github/workflows/release-portable.yml")
        self.assertTrue(workflow.exists(), f"{workflow} should exist")

        text = workflow.read_text(encoding="utf-8")
        self.assertIn("workflow_run:", text)
        self.assertIn('workflows: ["CI"]', text)
        self.assertIn("types: [completed]", text)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertIn("github.event.workflow_run.event == 'push'", text)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", text)
        self.assertIn("packaging/windows/build-portable.ps1", text)
        self.assertIn("packaging/macos/build-portable.sh", text)
        self.assertIn("macos-15", text)
        self.assertIn("macos-15-intel", text)
        self.assertIn("macos-portable", text)
        self.assertIn("macos-portable-arm64", text)
        self.assertIn("macos-portable-x64", text)
        self.assertIn("actions/upload-artifact", text)
        self.assertIn("actions/download-artifact", text)
        self.assertIn("Check out release notes", text)
        self.assertIn("ref: ${{ needs.resolve-release.outputs.checkout-ref }}", text)
        self.assertIn("GH_REPO: ${{ github.repository }}", text)
        self.assertIn("## 发布说明", text)
        self.assertIn('release_summary="$(awk', text)
        self.assertIn("/^当前版本：/ || /^本版重点：/", text)
        self.assertIn("/^本版详情：/", text)
        self.assertIn("in_details && /^## /", text)
        self.assertIn("${release_summary}", text)
        self.assertIn("此版本包含 iLab GPT Conjure 对应 tag 的源码和免安装一键包。", text)
        self.assertIn("完整版本说明见 [RELEASES.md](https://github.com/${GITHUB_REPOSITORY}/blob/${RELEASE_TAG}/RELEASES.md)。", text)
        self.assertIn("## 免安装一键包", text)
        self.assertIn('release_version="${RELEASE_TAG#v}"', text)
        self.assertIn("- Windows x64：ilab-gpt-conjure_windows_portable_x64_${release_version}.zip", text)
        self.assertNotIn("- Windows x64：`ilab-gpt-conjure_windows_portable_x64_${release_version}.zip`", text)
        self.assertNotIn("<version>", text)
        self.assertNotIn("Portable packages for iLab GPT Conjure.", text)
        self.assertIn("gh release edit", text)
        self.assertIn("gh release upload", text)


if __name__ == "__main__":
    unittest.main()
