import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Vault, TrendingUp, Shield, Zap, ArrowRight, ChevronRight } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="relative overflow-hidden">
      {/* Hero Section */}
      <section className="relative min-h-[80vh] flex items-center">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-background to-background" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-cyan-500/10 via-transparent to-transparent" />
        
        <div className="relative max-w-7xl mx-auto px-4 md:px-8 py-20 md:py-32">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 mb-6">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-sm text-primary font-medium">Live on Base</span>
            </div>
            
            <h1 className="text-5xl md:text-7xl font-bold leading-tight mb-6 tracking-tight" data-testid="hero-title">
              <span className="text-gradient">Maximize</span>
              <br />
              <span className="text-foreground">Your Yield</span>
            </h1>
            
            <p className="text-xl md:text-2xl text-muted-foreground leading-relaxed mb-10 max-w-xl">
              Deposit your LP tokens into auto-compounding vaults. 
              Let our strategies do the heavy lifting while you earn.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4">
              <Link to="/vaults">
                <Button size="lg" className="h-14 px-8 text-lg glow-primary glow-primary-hover" data-testid="explore-vaults-btn">
                  Explore Vaults
                  <ArrowRight className="w-5 h-5 ml-2" />
                </Button>
              </Link>
              <a href="https://docs.base.org" target="_blank" rel="noopener noreferrer">
                <Button variant="outline" size="lg" className="h-14 px-8 text-lg border-border/50 hover:border-primary/50">
                  Learn More
                </Button>
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 md:py-32 border-t border-border/50">
        <div className="max-w-7xl mx-auto px-4 md:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Why BaseVault?</h2>
            <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
              Built for serious yield farmers on Base
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <FeatureCard
              icon={TrendingUp}
              title="Auto-Compounding"
              description="Harvests are automatically reinvested to compound your returns over time."
            />
            <FeatureCard
              icon={Shield}
              title="Battle-Tested"
              description="Audited smart contracts with proven track record across multiple chains."
            />
            <FeatureCard
              icon={Zap}
              title="Gas Efficient"
              description="Optimized strategies that save you gas fees on every harvest."
            />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 md:py-32 border-t border-border/50">
        <div className="max-w-7xl mx-auto px-4 md:px-8 text-center">
          <div className="max-w-2xl mx-auto">
            <h2 className="text-3xl md:text-4xl font-bold mb-6">
              Ready to start earning?
            </h2>
            <p className="text-muted-foreground text-lg mb-10">
              Connect your wallet and deposit into a vault to start earning yield today.
            </p>
            <Link to="/vaults">
              <Button size="lg" className="h-14 px-10 text-lg glow-primary" data-testid="start-earning-btn">
                Start Earning
                <ChevronRight className="w-5 h-5 ml-2" />
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function FeatureCard({ icon: Icon, title, description }) {
  return (
    <div className="group p-8 rounded-2xl bg-card border border-border hover:border-primary/50 transition-all duration-300">
      <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center mb-6 group-hover:glow-primary transition-all">
        <Icon className="w-7 h-7 text-primary" />
      </div>
      <h3 className="text-xl font-bold mb-3">{title}</h3>
      <p className="text-muted-foreground leading-relaxed">{description}</p>
    </div>
  );
}
