var Template = class TemplateClass {

    element;
    iframeUrl;

    constructor(id, iframeUrl) {
        this.element = $(`#${id}`);
        this.iframeUrl = iframeUrl;
        window.addEventListener("message", this.receiveMessage);
    }

    open() {
        this.element.find('#template-iframe').attr('src', this.iframeUrl);
        this.element.show();
        $("html").css("overflow","hidden");
        $("body").css("overflow","hidden");
    }

    close() {
        this.element.find('#template-iframe').attr('src', 'about:blank');
        this.element.hide();
        $("html").css("overflow","auto");
        $("body").css("overflow","hidden");
    }

    receiveMessage = (event) => {

        try {
            var data = JSON.parse(event.data);

            switch (data.action) {
                case 'close':
                    this.close();
                    break;
            }
        } catch (e) {

        }

    }


}
var Slides = class SlideClass {

    translateX = 0;
    index = 0;
    slideElms;
    slideWidth;
    slidesElm;
    hammer;

    constructor(selector) {
        this.slidesElm = $(selector);
        this.hammer = new Hammer(this.slidesElm[0]);
        this.slideElms = this.slidesElm.eq(0).find('.slide');
        this.slideWidth = this.slideElms.eq(0).width();


        this.hammer.on('panleft panright', (ev) => {
            if (ev.isFinal) {
                return;
            }

            var moveX = this.translateX + ev.deltaX;
            var currentIndex = 0;

            if (ev.deltaX < 0) {
                currentIndex = -(this.index - Math.round(Math.abs(ev.deltaX) / this.slideWidth));
            } else {
                currentIndex = -(this.index + Math.round(Math.abs(ev.deltaX) / this.slideWidth));
            }


            if (currentIndex <= -1 || currentIndex >= this.slideElms.length) {

            } else {
                $(this.slideElms).css({'transform': 'translateX(' + moveX + 'px)'});
            }

        });
        this.hammer.on('panend', (ev) => {
            if (Math.abs(ev.deltaX) < (this.slideWidth / 2)) {
                this.moveSlide();
            } else {
                if (ev.deltaX < 0) {
                    this.index -= Math.round(Math.abs(ev.deltaX) / this.slideWidth);
                } else {
                    this.index += Math.round(Math.abs(ev.deltaX) / this.slideWidth);
                }

                if (-this.index <= -1) {
                    this.index = 0;
                } else if (-this.index >= this.slideElms.length) {
                    this.index = -(this.slideElms.length - 1);
                }
                this.translateX = this.slideWidth * this.index;
                this.moveSlide();
            }
        });

        this.slidesElm.find(".pagination li").each((i, elm) => {
            $(elm).on('click', () => {
                this.moveSlide(i);
            });
        });

    }


    moveSlide(moveIndex = null) {
        if (moveIndex != null) {
            this.translateX = -moveIndex * this.slideWidth;
        }
        $(this.slideElms).css({'transition': 'transform 0.45s ease'});
        $(this.slideElms).css({'transform': 'translateX(' + (this.translateX) + 'px)'});
        this.activePagenation(Math.abs(this.translateX / this.slideWidth));
        setTimeout(() => {
            $(this.slideElms).css({'transition': ''});
        }, 460);
    }

    activePagenation(pageIndex) {
        var pager = this.slidesElm.find(".pagination li a");
        pager.removeClass('active');
        pager.eq(pageIndex).addClass('active');
    }


}


window.addEventListener('load', () => {


    const calculateSize = () => {
        const height = Math.min(window.innerHeight, document.querySelectorAll('iframe')[0].offsetHeight );
        document.querySelectorAll('iframe')[0].contentWindow.postMessage(JSON.stringify({'resizedHeight': height}), '*');

    };

    document.getElementById('template-iframe').addEventListener('load',calculateSize);
    window.addEventListener('resize',calculateSize );
});
