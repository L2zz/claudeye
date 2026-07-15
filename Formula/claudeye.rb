# Homebrew formula for claudeye.
#
# From a tap:   brew install L2zz/tap/claudeye
# Or locally:   brew install --formula ./Formula/claudeye.rb
#
# claudeye is a zero-runtime-dependency Python package, so the formula
# installs it with Homebrew's python via a virtualenv and links the
# `claudeye` console script.
class Claudeye < Formula
  include Language::Python::Virtualenv

  desc "An eye on your Claude Code usage — find context-waste patterns locally"
  homepage "https://github.com/L2zz/claudeye"
  url "https://github.com/L2zz/claudeye/archive/refs/tags/v0.1.0.tar.gz"
  # Updated automatically in L2zz/homebrew-tap from published releases.
  sha256 "3fa0c7691919d126491d59edf5df3e2bba06d6c27da15f2e34445aa0b89f065b"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "claudeye", shell_output("#{bin}/claudeye --version")
  end
end
