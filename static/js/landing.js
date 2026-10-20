/**
 * Public landing page interactions.
 *
 *  - Hero scene parallax: the campus photograph and its colour orbs are
 *    translated from the scroll position, plus a subtle pointer offset.
 *    `data-speed` on the photo layer decides how slow it drifts; `data-depth`
 *    on each decoration decides how far it floats.
 *  - `[data-reveal]` elements fade/slide in once, staggered by `--reveal-delay`.
 *  - Header switches from transparent-over-hero to solid after scrolling.
 *  - Workflow rail fills and the current step lights up while scrolling.
 *
 * Only transform/opacity are touched, everything is batched on
 * requestAnimationFrame, and every motion effect is skipped entirely when the
 * visitor prefers reduced motion.
 */
(function () {
    'use strict';

    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    var hero = document.getElementById('hero');
    var heroContent = document.getElementById('hero-content');
    var heroCue = document.getElementById('hero-cue');
    var header = document.getElementById('site-header');
    var stepsWrap = document.getElementById('workflow-steps');
    var steps = Array.prototype.slice.call(document.querySelectorAll('.workflow-step'));

    var parallaxTargets = Array.prototype.slice.call(document.querySelectorAll('[data-parallax]'));
    var sceneLayers = parallaxTargets.filter(function (el) {
        return el.classList.contains('landing-layer');
    });
    var decorations = parallaxTargets.filter(function (el) {
        return !el.classList.contains('landing-layer');
    });

    var scrollY = window.scrollY || window.pageYOffset || 0;
    var viewportH = window.innerHeight;
    var pending = false;
    var pointer = { x: 0, y: 0, smoothX: 0, smoothY: 0 };

    function schedule() {
        if (pending) return;
        pending = true;
        window.requestAnimationFrame(render);
    }

    function heroInView() {
        if (!hero) return false;
        var rect = hero.getBoundingClientRect();
        return rect.bottom > 0 && rect.top < viewportH;
    }

    function render() {
        pending = false;

        // Header state runs regardless of motion preferences (it is a plain
        // colour transition, not movement).
        if (header) {
            header.classList.toggle('is-solid', scrollY > 36);
        }

        if (!reduceMotion.matches) {
            // --- Hero scene parallax ---------------------------------------
            if (hero && heroInView()) {
                var heroHeight = hero.offsetHeight || viewportH;

                pointer.smoothX += (pointer.x - pointer.smoothX) * 0.12;
                pointer.smoothY += (pointer.y - pointer.smoothY) * 0.12;

                sceneLayers.forEach(function (layer) {
                    // `data-speed` is the apparent scroll speed of the layer:
                    // 1 = moves with the page, < 1 = distant (slower), > 1 =
                    // foreground (faster). Offsetting by (1 - speed) * scrollY
                    // produces that speed, and the pointer tilt uses the same
                    // signed distance so near and far layers counter-move.
                    var speed = parseFloat(layer.getAttribute('data-speed'));
                    if (isNaN(speed)) speed = 1;
                    var py = (1 - speed) * scrollY + (speed - 1) * pointer.smoothY * 60;
                    var px = (speed - 1) * pointer.smoothX * 130;
                    layer.style.setProperty('--py', py.toFixed(2) + 'px');
                    layer.style.setProperty('--px', px.toFixed(2) + 'px');
                });

                if (heroContent) {
                    var progress = Math.min(Math.max(scrollY / (heroHeight * 0.9), 0), 1);
                    heroContent.style.setProperty('--py', (progress * 72).toFixed(1) + 'px');
                    heroContent.style.setProperty('--hero-opacity', (1 - progress * 0.92).toFixed(3));
                    if (heroCue) {
                        heroCue.style.opacity = Math.max(1 - progress * 1.6, 0).toFixed(3);
                    }
                }

                // Keep easing the pointer offset until it settles.
                var settled = Math.abs(pointer.x - pointer.smoothX) < 0.002 &&
                              Math.abs(pointer.y - pointer.smoothY) < 0.002;
                if (!settled) schedule();
            }

            // --- Section decorations drift as they cross the viewport ------
            decorations.forEach(function (el) {
                var rect = el.getBoundingClientRect();
                if (rect.bottom < -160 || rect.top > viewportH + 160) return;
                var depth = parseFloat(el.getAttribute('data-depth')) || 0.08;
                var travel = (viewportH - rect.top) / (viewportH + rect.height);
                el.style.setProperty('--py', ((travel - 0.5) * depth * 320).toFixed(1) + 'px');
            });
        }

        // --- Workflow progress rail ----------------------------------------
        if (stepsWrap) {
            var wrapRect = stepsWrap.getBoundingClientRect();
            if (wrapRect.bottom > 0 && wrapRect.top < viewportH) {
                var start = viewportH * 0.72;
                var end = viewportH * 0.32;
                var span = wrapRect.height + (start - end);
                var ratio = span > 0 ? (start - wrapRect.top) / span : 0;
                ratio = Math.min(Math.max(ratio, 0), 1);
                stepsWrap.style.setProperty('--progress', ratio.toFixed(3));

                var line = viewportH * 0.58;
                var active = null;
                steps.forEach(function (step) {
                    if (!active && step.getBoundingClientRect().bottom > line) {
                        active = step;
                    }
                });
                steps.forEach(function (step) {
                    step.classList.toggle('is-active', step === active);
                });
            }
        }
    }

    window.addEventListener('scroll', function () {
        scrollY = window.scrollY || window.pageYOffset || 0;
        schedule();
    }, { passive: true });

    window.addEventListener('resize', function () {
        viewportH = window.innerHeight;
        schedule();
    }, { passive: true });

    // Pointer tilt is desktop-only and follows the cursor with a light easing.
    if (hero && window.matchMedia('(pointer: fine)').matches && !reduceMotion.matches) {
        hero.addEventListener('pointermove', function (event) {
            var rect = hero.getBoundingClientRect();
            pointer.x = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
            pointer.y = ((event.clientY - rect.top) / rect.height - 0.5) * 2;
            schedule();
        });
        hero.addEventListener('pointerleave', function () {
            pointer.x = 0;
            pointer.y = 0;
            schedule();
        });
    }

    // --- Scroll reveals ----------------------------------------------------
    var revealTargets = Array.prototype.slice.call(document.querySelectorAll('[data-reveal]'));

    if (reduceMotion.matches || !('IntersectionObserver' in window)) {
        revealTargets.forEach(function (el) { el.classList.add('is-revealed'); });
    } else {
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-revealed');
                observer.unobserve(entry.target);
            });
        }, { threshold: 0.15, rootMargin: '0px 0px -8% 0px' });
        revealTargets.forEach(function (el) { observer.observe(el); });
    }

    schedule();
})();
