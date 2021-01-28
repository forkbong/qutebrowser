# Maintainer: Florian Bruhin (The Compiler) <archlinux.org@the-compiler.org>
# Contributor: Morten Linderud <foxboron@archlinux.org>
# Contributor: Pierre Neidhardt <ambrevar@gmail.com>
# vim: set ts=4 sw=4 et ft=sh:

pkgname=qutebrowser-fork-git
pkgver=2.0.0.r12.g4294ebe1a
pkgrel=1
pkgdesc="A keyboard-driven, vim-like browser based on PyQt5"
arch=("any")
url="https://www.qutebrowser.org/"
license=("GPL")
depends=("python-jinja" "python-pyqt5" "python-yaml" "qt5-base" "python-pyqtwebengine"
         "ttf-font-icons" "pdfjs" "python-adblock")
makedepends=("asciidoc" "pygmentize" "git" "python-setuptools")
optdepends=("gst-libav: media playback with qt5-webkit backend"
            "gst-plugins-base: media playback with qt5-webkit backend"
            "gst-plugins-good: media playback with qt5-webkit backend"
            "gst-plugins-bad: media playback with qt5-webkit backend"
            "gst-plugins-ugly: media playback with qt5-webkit backend"
            "python-pygments: :view-source with qt5-webkit backend"
            "qt5-webkit: alternative backend")
options=(!emptydirs)
conflicts=('qutebrowser')
provides=('qutebrowser')
source=('git+https://github.com/forkbong/qutebrowser.git#branch=fork')
sha256sums=('SKIP')

pkgver() {
    cd "$srcdir/qutebrowser"
    # Minor releases are not part of the master branch
    _tag=$(git tag --sort=v:refname | tail -n1)
    printf '%s.r%s.g%s' "${_tag#v}" "$(git rev-list "$_tag"..HEAD --count)" "$(git rev-parse --short HEAD)"
}

build() {
    cd "$srcdir/qutebrowser"
    python scripts/asciidoc2html.py
    a2x -f manpage doc/qutebrowser.1.asciidoc
    python setup.py build
}

package() {
    cd "$srcdir/qutebrowser"
    make -f misc/Makefile DESTDIR="$pkgdir" PREFIX=/usr install
}