// 校园活动管理系统 V1.0 - 全局脚本
(function () {
    'use strict';

    // DOM Ready 工具
    function ready(fn) {
        if (document.readyState !== 'loading') fn();
        else document.addEventListener('DOMContentLoaded', fn);
    }

    // 自动隐藏 flash 消息
    ready(function () {
        var flashes = document.querySelectorAll('.flash-container .alert');
        flashes.forEach(function (el) {
            setTimeout(function () {
                el.style.transition = 'opacity 0.6s';
                el.style.opacity = '0';
                setTimeout(function () { el.remove(); }, 600);
            }, 4000);
        });
    });

    // 暴露给模板使用
    window.CampusActivity = {
        confirm: function (message) {
            return confirm(message);
        }
    };
})();