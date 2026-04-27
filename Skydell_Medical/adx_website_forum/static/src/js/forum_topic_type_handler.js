/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Handles topic type selection on the new forum post form.
 * When a topic type is selected, its description is loaded
 * into the OdooEditor content area.
 */
publicWidget.registry.ForumTopicTypeHandler = publicWidget.Widget.extend({
    selector: ".website_forum",
    events: {
        "change #topic_type_select": "_onTopicTypeChange",
    },

    _onTopicTypeChange(ev) {
        const select = ev.currentTarget;
        const option = select.options[select.selectedIndex];
        const description = option.dataset.description || "";

        this._setEditorContent(description);
    },

    _setEditorContent(content) {
        // Try to find the OdooEditor editable area (Odoo 18 standard)
        const editable = this.el.querySelector("label[for='content'] + * .odoo-editor-editable");
        if (editable) {
            editable.innerHTML = content;
            // Dispatch input event so OdooEditor tracks the change in its history
            editable.dispatchEvent(new Event("input", { bubbles: true }));
            return;
        }

        // Editor not yet mounted — set on the textarea so loadWysiwygFromTextarea
        // picks it up as the initial value via the content attribute
        const textarea = this.el.querySelector("textarea[name='content']");
        if (textarea) {
            textarea.value = content;
            textarea.setAttribute("content", content);
        }
    },
});
