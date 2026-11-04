//! A visible, client-scoped confirmation for Zellij's native Quit action.
//!
//! Adapted from qdelettre/zellij-confirm at
//! 9d15b816523b92d98bcff0d921030ff26a044abf; see LICENSE.
use std::collections::BTreeMap;
use zellij_tile::prelude::*;

#[derive(Default)]
struct State {
    permission_granted: bool,
    question_rendered: bool,
    finished: bool,
}

register_plugin!(State);

impl ZellijPlugin for State {
    fn load(&mut self, _configuration: BTreeMap<String, String>) {
        // Do not subscribe to keys while the permission question is active.
        // Its "y" must grant permission, never also approve quitting.
        subscribe(&[EventType::PermissionRequestResult]);
        request_permission(&[PermissionType::ChangeApplicationState]);
    }

    fn update(&mut self, event: Event) -> bool {
        if self.finished {
            return false;
        }
        match event {
            Event::PermissionRequestResult(PermissionStatus::Granted) => {
                self.permission_granted = true;
                self.question_rendered = false;
                subscribe(&[EventType::Key]);
                true
            }
            Event::PermissionRequestResult(PermissionStatus::Denied) => {
                self.finished = true;
                close_self();
                false
            }
            Event::Key(key) if key.has_no_modifiers() => {
                match key.bare_key {
                    BareKey::Char('n') | BareKey::Esc => {
                        self.finished = true;
                        close_self();
                    }
                    BareKey::Char('y') if self.permission_granted && self.question_rendered => {
                        self.finished = true;
                        // This is the native client Quit, not kill_sessions().
                        // Other attached clients continue; the last client
                        // leaving through Quit ends the session.
                        quit_zellij();
                        close_self();
                    }
                    _ => {}
                }
                false
            }
            _ => false,
        }
    }

    fn render(&mut self, rows: usize, cols: usize) {
        if !self.permission_granted || self.finished {
            return;
        }
        self.question_rendered = false;
        if rows < 3 || cols < 26 {
            for line in ["Enlarge terminal", "n/Esc: cancel"].iter().take(rows) {
                println!("{}", line.chars().take(cols).collect::<String>());
            }
            return;
        }
        let lines = [
            "Quit Zellij?",
            "Last client: running programs stop.",
            "y: quit    n / Esc: cancel",
        ];
        let top = rows.saturating_sub(lines.len()) / 2;
        for _ in 0..top {
            println!();
        }
        for line in lines.iter().take(rows.saturating_sub(top)) {
            // ASCII text remains readable even without patched fonts; clipping
            // also avoids accidental wraps in a very narrow terminal.
            let text: String = line.chars().take(cols).collect();
            let left = cols.saturating_sub(text.len()) / 2;
            println!("{}{}", " ".repeat(left), text);
        }
        self.question_rendered = true;
    }
}
