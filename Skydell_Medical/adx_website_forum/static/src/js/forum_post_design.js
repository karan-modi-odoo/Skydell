/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

/**
 * Handles copy link and separate like/dislike counters
 * for the custom forum post actions toolbar.
 */
publicWidget.registry.ForumCopyLink = publicWidget.Widget.extend({
    selector: '.o_wforum_wrapper',
    events: {
        'click .skd-copy-link-btn': '_onCopyLink',
        'click .vote_up:not(.karma_required)': '_onUpvoteClick',
        'click .vote_down:not(.karma_required)': '_onDownvoteClick',
    },
    async start() {
        await this._super(...arguments);
        let html_editors = document.getElementsByClassName("odoo-editor-editable");
        setTimeout(function() {
            for (let i = 0; i < html_editors.length; i++) {
                html_editors[i].style.height = '200px';
            }
        }, 2000);

    },

    /**
     * Copy current page URL to clipboard.
     */
    _onCopyLink(ev) {
        const btn = ev.currentTarget;
        navigator.clipboard.writeText(window.location.href).then(() => {
            btn.innerHTML = '<i class="fa fa-check"></i>';
            setTimeout(() => {
                btn.innerHTML = '<i class="fa fa-link"></i>';
            }, 2000);
        });
    },

    /**
     * Handle upvote click — update like counter after RPC.
     */
    _onUpvoteClick(ev) {
        const btn = ev.currentTarget;
        const container = btn.closest('.vote');
        if (!container) return;
        const href = btn.dataset.href;
        if (!href) return;
        rpc(href).then((data) => {
            if (data && !data.error) {
                this._updateCounters(container, data, 'up');
            }
        });
    },

    /**
     * Handle downvote click — update dislike counter after RPC.
     */
    _onDownvoteClick(ev) {
        const btn = ev.currentTarget;
        const container = btn.closest('.vote');
        if (!container) return;
        const href = btn.dataset.href;
        if (!href) return;
        rpc(href).then((data) => {
            if (data && !data.error) {
                this._updateCounters(container, data, 'down');
            }
        });
    },

    /**
     * Update skd-like-count and skd-dislike-count separately.
     * userVote = 1 (liked), -1 (disliked), 0 (removed vote)
     * direction = 'up' or 'down' (which button was clicked)
     */
    _updateCounters(container, data, direction) {
        const likeCountEl = container.querySelector('.skd-like-count');
        const dislikeCountEl = container.querySelector('.skd-dislike-count');
        const voteUp = container.querySelector('.vote_up');
        const voteDown = container.querySelector('.vote_down');

        if (!likeCountEl || !dislikeCountEl) return;

        const userVote = parseInt(data.user_vote);
        const currentLike = parseInt(likeCountEl.textContent.trim()) || 0;
        const currentDislike = parseInt(dislikeCountEl.textContent.trim()) || 0;
        const wasLiked = voteUp.classList.contains('skd-like-active');
        const wasDisliked = voteDown.classList.contains('skd-dislike-active');

        if (userVote === 1) {
            // New like applied
            likeCountEl.textContent = currentLike + 1;
            // If was previously disliked, remove dislike count
            if (wasDisliked) {
                dislikeCountEl.textContent = Math.max(0, currentDislike - 1);
                voteDown.classList.remove('skd-dislike-active');
            }
            voteUp.classList.add('skd-like-active');
        } else if (userVote === -1) {
            // New dislike applied
            dislikeCountEl.textContent = currentDislike + 1;
            // If was previously liked, remove like count
            if (wasLiked) {
                likeCountEl.textContent = Math.max(0, currentLike - 1);
                voteUp.classList.remove('skd-like-active');
            }
            voteDown.classList.add('skd-dislike-active');
        } else {
            // Vote removed (toggled off)
            if (direction === 'up' && wasLiked) {
                likeCountEl.textContent = Math.max(0, currentLike - 1);
                voteUp.classList.remove('skd-like-active');
            } else if (direction === 'down' && wasDisliked) {
                dislikeCountEl.textContent = Math.max(0, currentDislike - 1);
                voteDown.classList.remove('skd-dislike-active');
            }
        }
    },
});