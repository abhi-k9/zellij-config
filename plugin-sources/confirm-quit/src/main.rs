//! A visible, client-scoped confirmation for Zellij's native Quit action.
//!
//! Adapted from qdelettre/zellij-confirm at
//! 9d15b816523b92d98bcff0d921030ff26a044abf; see LICENSE.
use std::collections::BTreeMap;
use zellij_tile::prelude::*;

#[derive(Default)]
struct State {
    status_style: bool,
    invalid_style: bool,
    permission_granted: bool,
    question_rendered: bool,
    finished: bool,
    active_tab: Option<TabInfo>,
    panes: Option<PaneManifest>,
    status_geometry: Option<(usize, usize)>,
}

register_plugin!(State);

impl ZellijPlugin for State {
    fn load(&mut self, configuration: BTreeMap<String, String>) {
        match configuration.get("display_style").map(String::as_str).unwrap_or("popup") {
            "popup" => {},
            "status" => self.status_style = true,
            _ => self.invalid_style = true,
        }
        // Do not subscribe to keys while the permission question is active.
        // Its "y" must grant permission, never also approve quitting.
        subscribe(&[EventType::PermissionRequestResult]);
        let mut permissions = vec![PermissionType::ChangeApplicationState];
        if self.status_style {
            // Subscribe before requesting permission so the host can replay
            // its initial tab/pane state when permission is granted. Waiting
            // until the grant can leave us without state until a layout change.
            subscribe(&[EventType::TabUpdate, EventType::PaneUpdate]);
            permissions.push(PermissionType::ReadApplicationState);
        }
        request_permission(&permissions);
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
                self.place_status_line();
                true
            }
            Event::PermissionRequestResult(PermissionStatus::Denied) => {
                self.finished = true;
                close_self();
                false
            }
            Event::TabUpdate(tabs) if self.status_style => {
                self.active_tab = tabs.into_iter().find(|tab| tab.active);
                self.place_status_line();
                true
            }
            Event::PaneUpdate(panes) if self.status_style => {
                self.panes = Some(panes);
                self.place_status_line();
                true
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
        if self.invalid_style {
            println!("Invalid display_style; n/Esc: cancel");
            return;
        }
        if self.status_style {
            if self.status_geometry.is_none() || rows != 1 {
                println!("Preparing confirmation; n/Esc: cancel");
                return;
            }
            let line = "Quit Zellij?  y: quit  n/Esc: cancel";
            if rows == 0 || cols < line.len() {
                println!("{}", "Enlarge terminal; n/Esc: cancel".chars().take(cols).collect::<String>());
                return;
            }
            print!("{}", line);
            self.question_rendered = true;
            return;
        }
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

impl State {
    fn place_status_line(&mut self) {
        if !self.permission_granted || self.finished {
            return;
        }
        let (Some(tab), Some(manifest)) = (&self.active_tab, &self.panes) else { return; };
        let Some(panes) = manifest.panes.get(&tab.position) else { return; };
        let own_id = get_plugin_ids().plugin_id;
        let bar = panes.iter().find(|pane| pane.is_plugin && pane.id != own_id
            && !pane.is_floating && !pane.is_suppressed
            && pane.pane_rows == 1 && pane.pane_columns == tab.display_area_columns
            && pane.pane_y + pane.pane_rows == tab.display_area_rows);
        let y = bar.map(|bar| bar.pane_y).unwrap_or(tab.display_area_rows).saturating_sub(1);
        let width = tab.viewport_columns;
        if width == 0 || tab.viewport_rows == 0 || self.status_geometry == Some((y, width)) {
            return;
        }
        self.status_geometry = Some((y, width));
        self.question_rendered = false;
        // A one-row overlay leaves the original bar, tiled pane geometry and
        // processes intact. Closing the plugin reveals the underlying row.
        let mut coordinates = FloatingPaneCoordinates::default()
            .with_x_fixed(0).with_y_fixed(y).with_width_fixed(width)
            .with_height_fixed(1);
        coordinates.pinned = Some(true);
        coordinates.borderless = Some(true);
        change_floating_panes_coordinates(vec![(PaneId::Plugin(own_id), coordinates)]);
    }
}
