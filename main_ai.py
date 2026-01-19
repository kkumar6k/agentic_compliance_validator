"""
AI-Powered Compliance Validator
Main entry point using LangGraph multi-agent system with RAG

Usage:
    python main_ai.py [invoice_id]
    python main_ai.py --batch
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import date

from agents.langgraph_workflow import ComplianceWorkflow
from agents.reporter import ReporterAgent
from utils.data_loaders import InvoiceDataLoader
from utils.validators import InvoiceValidator, validate_invoice
import os
from pathlib import Path
from dotenv import load_dotenv

# Explicitly load .env from project root
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Verify
api_key = os.getenv('OPENAI_API_KEY')
if not api_key or not api_key.startswith('sk-proj-'):
    raise ValueError(f"Invalid OPENAI_API_KEY. Got: {api_key[:20] if api_key else 'None'}...")


class AIComplianceValidator:
    """
    AI-Powered compliance validator using LangGraph + RAG
    """

    def __init__(self):
        print("🤖 Initializing AI-Powered Compliance Validator...")
        print("   • Loading LangGraph workflow...")
        self.workflow = ComplianceWorkflow()

        print("   • Loading RAG systems...")
        # RAG systems initialized in agents

        print("   • Loading reporter...")
        self.reporter = ReporterAgent()

        print("   • Loading test data...")
        self.invoice_loader = InvoiceDataLoader()

        print("✅ AI system ready!\n")

    async def validate_single(self, invoice_id: str):
        """Validate single invoice using AI agents"""

        print(f"\n{'='*80}")
        print(f"🤖 AI-POWERED COMPLIANCE VALIDATION")
        print(f"{'='*80}\n")

        # Load invoice with error handling
        try:
            invoice_json = self.invoice_loader.get_invoice(invoice_id)
        except ValueError as e:
            print(f"❌ Error loading invoice: {e}")
            return
        except Exception as e:
            print(f"❌ Unexpected error loading invoice: {e}")
            import traceback
            traceback.print_exc()
            return

        print(f"📄 Invoice: {invoice_id}")
        print(f"   Category: {invoice_json.get('_test_category', 'N/A')}")
        print(f"   Complexity: {invoice_json.get('_complexity', 'N/A')}")

        # Validate invoice data structure
        print("\n🔍 Validating invoice data structure...")
        validation_result = validate_invoice(invoice_json)

        if not validation_result:
            print(f"❌ VALIDATION FAILED - Invoice has malformed data:")
            for i, error in enumerate(validation_result.errors, 1):
                print(f"   {i}. {error}")
            print(f"\n⚠️  Cannot process malformed invoice. Fix data and retry.")
            return

        print(f"✅ Invoice data validation passed")

        # Display invoice details
        try:
            print(f"   Amount: ₹{invoice_json['total_amount']:,.2f}")
        except (KeyError, TypeError, ValueError):
            print(f"   Amount: Unable to parse")
        print()

        # Pass invoice data to workflow (workflow will handle transformation)
        invoice_data = invoice_json

        # Run LangGraph workflow
        print("🔄 Running LangGraph multi-agent workflow...")
        print("   ├─► Supervisor Agent (orchestrating)")
        print("   ├─► Arithmetic Agent (rule-based)")
        print("   ├─► GST Agent (LLM + RAG)")
        print("   ├─► Vendor Agent (lookups)")
        print("   ├─► TDS Agent (rule-based)")
        print("   ├─► Policy Agent (rule-based)")
        print("   ├─► Resolver Agent (LLM analysis)")
        print("   └─► Reporter Agent")
        print()

        try:
            final_state = await self.workflow.run(invoice_id, invoice_data)
        except KeyError as e:
            print(f"❌ Missing data in workflow: {e}")
            print(f"   This may indicate a data structure issue.")
            print(f"\n🔍 FULL ERROR TRACEBACK:")
            import traceback
            traceback.print_exc()
            print(f"\n📋 Debug Info:")
            print(f"   - Invoice ID: {invoice_id}")
            print(f"   - Has 'vendor': {'vendor' in invoice_data}")
            print(f"   - Has 'buyer': {'buyer' in invoice_data}")
            if 'vendor' in invoice_data:
                print(f"   - vendor keys: {list(invoice_data['vendor'].keys())}")
            return
        except ValueError as e:
            print(f"❌ Invalid data value: {e}")
            return
        except ConnectionError as e:
            print(f"❌ Network error (API call failed): {e}")
            print(f"   Check your OPENAI_API_KEY and internet connection.")
            return
        except Exception as e:
            print(f"❌ Workflow error: {e}")
            print(f"\n🔧 Debug information:")
            print(f"   Invoice ID: {invoice_id}")
            print(f"   Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            return

        # Display results
        print(f"\n{'='*80}")
        print("VALIDATION RESULTS")
        print(f"{'='*80}\n")

        print(f"Overall Status: {final_state['overall_status']}")
        print(f"Confidence: {final_state['confidence_score']:.0%}")
        print(f"Total Checks: {len(final_state['all_checks'])}")
        print(f"Passed: {final_state['passed_checks']}")
        print(f"Failed: {final_state['failed_checks']}")
        print(f"Warnings: {final_state['warning_checks']}")
        print()

        if final_state.get('escalation_needed'):
            print("🚨 ESCALATION REQUIRED")
            print("Reasons:")
            for reason in final_state['escalation_reasons']:
                print(f"  • {reason}")
            print()

        if final_state.get('final_decision'):
            print("🤖 AI ANALYSIS:")
            print(final_state['final_decision'])
            print()

        # Show key failures
        failed_checks = [c for c in final_state['all_checks'] if c['status'] == 'FAIL']
        if failed_checks:
            print("❌ FAILED CHECKS:")
            for check in failed_checks:
                print(f"  • {check['check_id']}: {check['check_name']}")
                print(f"    {check['reasoning'][:100]}")
            print()

        # Show LLM-powered checks
        llm_checks = [c for c in final_state['all_checks'] if c.get('agent_type') == 'llm_powered']
        if llm_checks:
            print("🤖 LLM-POWERED ANALYSIS:")
            for check in llm_checks:
                print(f"  • {check['check_id']}: {check['check_name']}")
                print(f"    Status: {check['status']}")
                print(f"    {check['reasoning'][:150]}...")
            print()

        # Save report
        report_file = Path("reports") / f"{invoice_id}_ai_report.json"

        try:
            report_file.parent.mkdir(exist_ok=True)

            with open(report_file, 'w') as f:
                # Remove non-serializable items
                save_state = {
                    k: v for k, v in final_state.items()
                    if k not in ['messages', 'processing_started'] and v is not None
                }
                json.dump(save_state, f, indent=2, default=str)

            print(f"💾 Full report saved: {report_file}")
        except PermissionError:
            print(f"⚠️  Could not save report: Permission denied")
        except Exception as e:
            print(f"⚠️  Could not save report: {e}")

        print(f"\n{'='*80}\n")

    async def validate_batch(self, count: int = 5):
        """Validate multiple invoices"""

        print(f"\n{'='*80}")
        print(f"🤖 AI-POWERED BATCH VALIDATION")
        print(f"{'='*80}\n")

        # Get test invoices
        invoices = self.invoice_loader.invoices[:count]
        print(f"Processing {len(invoices)} invoices...\n")

        results = []
        for i, inv_json in enumerate(invoices, 1):
            print(f"[{i}/{len(invoices)}] {inv_json['invoice_id']}... ", end='', flush=True)

            try:
                # Pass original invoice_json (workflow will transform)
                invoice_data = inv_json
                state = await self.workflow.run(inv_json['invoice_id'], invoice_data)

                status_symbol = '✅' if state['overall_status'] == 'PASS' else '❌'
                print(f"{status_symbol} {state['overall_status']} ({state['confidence_score']:.0%})")

                results.append({
                    'invoice_id': inv_json['invoice_id'],
                    'status': state['overall_status'],
                    'confidence': state['confidence_score'],
                    'passed': state['passed_checks'],
                    'failed': state['failed_checks'],
                    'llm_used': state.get('requires_llm_reasoning', False)
                })

            except Exception as e:
                print(f"❌ ERROR: {str(e)[:50]}")
                results.append({
                    'invoice_id': inv_json['invoice_id'],
                    'status': 'ERROR',
                    'error': str(e)
                })

        # Summary
        print(f"\n{'='*80}")
        print("BATCH SUMMARY")
        print(f"{'='*80}\n")

        passed = len([r for r in results if r.get('status') == 'PASS'])
        failed = len([r for r in results if r.get('status') in ['FAIL', 'PASS_WITH_WARNINGS']])
        errors = len([r for r in results if r.get('status') == 'ERROR'])
        llm_used = len([r for r in results if r.get('llm_used', False)])

        print(f"Total: {len(results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Errors: {errors}")
        print(f"Used LLM Reasoning: {llm_used}")

        if results:
            avg_confidence = sum([r.get('confidence', 0) for r in results if 'confidence' in r]) / len([r for r in results if 'confidence' in r])
            print(f"Average Confidence: {avg_confidence:.0%}")

        print(f"\n{'='*80}\n")


async def main():
    """Main entry point"""

    validator = AIComplianceValidator()

    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg == '--batch':
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            await validator.validate_batch(count)
        elif arg == '--help':
            print("""
AI-Powered Compliance Validator

Single Invoice:
    python main_ai.py [invoice_id]
    Example: python main_ai.py INV-2024-0001

Batch Processing:
    python main_ai.py --batch [count]
    Example: python main_ai.py --batch 5

Features:
    • LangGraph multi-agent orchestration
    • RAG for GST/TDS regulations
    • LLM-powered complex case analysis
    • Automatic escalation logic
""")
        else:
            await validator.validate_single(arg)
    else:
        # Default
        await validator.validate_single("INV-2024-0001")


if __name__ == "__main__":
    asyncio.run(main())