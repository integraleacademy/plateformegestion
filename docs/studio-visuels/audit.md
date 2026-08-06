# Audit de référence — Studio visuel

> État audité après le revert `287a8fc`, avant les améliorations DOM.

## Architecture existante

- Route : `/admin/studio-visuels` dans `app.py`.
- Vue : `templates/admin/studio_visuals/editor.html`.
- État et historique : `studio-store.js`; sauvegarde différée via `studio-autosave.js` vers `/api/admin/social-visuals`.
- Rendu : DOM HTML dans `studio-renderer.js`; export inchangé via html-to-image 1.11.11 dans `studio-exporter.js`.
- Canvas logique : formats 1080×1080, 1080×1350, 1080×1920 et 1200×627; zoom CSS par transformation du canvas.
- Médias : endpoint existant `/api/admin/studio/media`, stockage persistant `data/studio_media`; seuls identifiant, URL et cadrage sont conservés.
- Texte : `studio-text-fit.js` attend les polices et ajuste les seules zones portant `data-fit`.

## Classement initial des templates

- `typographic_poster_center` — **design à améliorer**
- `typographic_poster_offset` — **design à améliorer**
- `editorial_split_columns` — **problème mineur de mise en page**
- `editorial_diagonal` — **problème mineur de mise en page**
- `session_calendar` — **problème important de mise en page**
- `session_ticket` — **problème mineur de mise en page**
- `session_countdown` — **design à améliorer**
- `stats_dashboard` — **design à améliorer**
- `stats_big_number` — **design à améliorer**
- `stats_bars` — **design à améliorer**
- `stats_radial_gauge` — **design à améliorer**
- `process_vertical_timeline` — **problème mineur de mise en page**
- `process_horizontal_timeline` — **problème mineur de mise en page**
- `process_staircase` — **design à améliorer**
- `process_route` — **design à améliorer**
- `program_modules_grid` — **problème mineur de mise en page**
- `program_editorial_index` — **problème mineur de mise en page**
- `comparison_face_to_face` — **problème mineur de mise en page**
- `comparison_before_after` — **problème important de mise en page**
- `faq_stacked_cards` — **problème mineur de mise en page**
- `faq_true_false` — **design à améliorer**
- `careers_constellation` — **design à améliorer**
- `quote_manifesto` — **design à améliorer**
- `carousel_final_cta` — **design à améliorer**
- `saas_metric_wall` — **design à améliorer**
- `saas_kpi_cards` — **design à améliorer**
- `saas_growth_bars` — **design à améliorer**
- `saas_success_gauge` — **design à améliorer**
- `giant_success_rate` — **design à améliorer**
- `giant_places_left` — **problème important de mise en page**
- `giant_countdown` — **design à améliorer**
- `almost_full_alert` — **design à améliorer**
- `new_session_open` — **design à améliorer**
- `opening_date_hero` — **design à améliorer**
- `exam_date_focus` — **problème mineur de mise en page**
- `timeline_dates` — **problème mineur de mise en page**
- `session_route_visual` — **design à améliorer**
- `launch_split_saas` — **problème mineur de mise en page**
- `proof_dashboard` — **design à améliorer**
- `proof_big_quote` — **design à améliorer**
- `conversion_final_places` — **design à améliorer**
- `conversion_booking_date` — **design à améliorer**
- `saas_pricing_metric` — **design à améliorer**
- `visual_modules_numbers` — **design à améliorer**
- `visual_stair_numbers` — **design à améliorer**
- `visual_before_after_rate` — **problème mineur de mise en page**
- `faq_places_open` — **problème mineur de mise en page**
- `cover_giant_acronym` — **design à améliorer**
- `cover_date_badge` — **design à améliorer**
- `session_capacity_cards` — **problème mineur de mise en page**
- `session_calendar_open` — **problème mineur de mise en page**
- `stats_completion_alert` — **design à améliorer**
- `stats_success_wall` — **design à améliorer**
- `stats_big_date` — **design à améliorer**
- `saas_waitlist` — **design à améliorer**
- `launch_ticket_premium` — **design à améliorer**
- `dates_calendar_premium` — **design à améliorer**
- `proof_constellation` — **design à améliorer**
- `urgency_diagonal` — **design à améliorer**
- `saas_final_cta` — **design à améliorer**

## Artefacts visuels

Les captures automatisées sont produites par le test navigateur dans `artifacts/studio-visuels/` lorsque Chromium et une session administrateur sont disponibles. Elles ne sont pas versionnées afin de ne pas gonfler le dépôt.
