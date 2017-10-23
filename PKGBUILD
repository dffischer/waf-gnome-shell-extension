# Maintainer: XZS <d dot f dot fischer at web dot de>
pkgname=waf-gnome-shell-extension-git
pkgver=r0
pkgrel=1
pkgdesc="A waf tool to install gnome-shell extensions"
arch=('any')
url="https://github.com/dffischer/${pkgname%-git}"
license=('GPL')
depends=('waf' 'gnome-shell')

# template input; name=git

build() {
	cd "$_gitname"
	waf --prefix=/usr configure build
}

package() {
	cd "$_gitname"
	waf install --destdir="$pkgdir/"
}
