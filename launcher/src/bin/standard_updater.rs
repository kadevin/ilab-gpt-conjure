use ilab_conjure_launcher::standard_update::{
    cleanup_standard_updater_handoff, run_standard_updater, show_standard_update_error,
    standard_update_locale_hint,
};

fn main() {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    let locale = standard_update_locale_hint(&args).to_string();
    let result = run_standard_updater(args);
    if let Err(error) = &result {
        show_standard_update_error(&format!("{error:#}"), &locale);
    }
    cleanup_standard_updater_handoff();
    if result.is_err() {
        std::process::exit(1);
    }
}
